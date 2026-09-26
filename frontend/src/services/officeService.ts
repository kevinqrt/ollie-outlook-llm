/**
 * First name from an Outlook display name - "Sören Müller" -> "Sören",
 * "Müller, Sören" -> "Sören". Empty for missing names or bare addresses.
 */
function firstName(displayName: string | undefined): string {
  const name = displayName?.trim() ?? '';
  if (!name || name.includes('@')) return '';
  if (name.includes(','))
    return name.split(',')[1]?.trim().split(/\s+/)[0] ?? '';
  return name.split(/\s+/)[0];
}

/**
 * Infrastruktur-Service: Kapselt ausschliesslich OfficeJS-Interaktionen.
 */
export class OfficeService {
  public async getBodyText(): Promise<string> {
    return new Promise((resolve, reject) => {
      const item = Office.context.mailbox.item;
      if (!item) return reject(new Error('Kein Element ausgewählt.'));
      item.body.getAsync(Office.CoercionType.Text, (result) => {
        if (result.status === Office.AsyncResultStatus.Succeeded) {
          resolve(result.value);
        } else {
          reject(new Error('Fehler beim Lesen des Bodys.'));
        }
      });
    });
  }

  /** Fügt `text` am Cursor ein - nur für den allerersten Einfüge-Versuch. */
  public async insertText(text: string): Promise<void> {
    const item = Office.context.mailbox.item;
    if (!item || !('body' in item)) {
      throw new Error('Schreibzugriff nicht möglich.');
    }

    return new Promise((resolve, reject) => {
      const htmlText = text.replace(/\n/g, '<br>');
      item.body.setSelectedDataAsync(
        htmlText,
        { coercionType: Office.CoercionType.Html },
        (result) => {
          if (result.status === Office.AsyncResultStatus.Succeeded) {
            resolve();
          } else {
            // Fallback auf Text
            item.body.setSelectedDataAsync(
              text,
              { coercionType: Office.CoercionType.Text },
              (res) => {
                if (res.status === Office.AsyncResultStatus.Succeeded)
                  resolve();
                else reject(new Error('Einfügen fehlgeschlagen.'));
              }
            );
          }
        }
      );
    });
  }

  /**
   * Ersetzt den kompletten Entwurf durch `text` - keine Suche, kein Anker,
   * kein Versuch mehr, irgendetwas vom vorherigen Inhalt (alte KI-Antwort
   * oder zitierter Original-Verlauf) zu erhalten. Frühere Versionen haben
   * versucht, nur die alte Antwort zu ersetzen und den Rest (den zitierten
   * Verlauf) zu erhalten - das ist am Ende an zwei Dingen gescheitert: Outlooks
   * internes Dokumentmodell hat eigene Marker (Attribut wie Kommentar)
   * zuverlässig verloren, und ein reiner Text-Anker hat zwar die alte Antwort
   * gefunden, dabei aber Outlooks eigene HTML-Formatierung des zitierten
   * Verlaufs plattgewalzt und bei mehrstufigen Threads unnötig viele alte
   * Rohdaten (Adressen, Zeitstempel) mit durchgereicht. Der Body enthält nach
   * dieser Methode ausschließlich die neue Antwort - bewusste, bestätigte
   * Design-Entscheidung.
   *
   * Schlägt das Schreiben selbst fehl (seltener Office.js-Fehlerfall), wird
   * als letzte Notlösung stattdessen am Cursor eingefügt (`insertText`); der
   * Rückgabewert `'inserted'` markiert genau diesen - dann tatsächlich
   * unvollständigen - Fall.
   */
  public async replaceInsertedText(
    text: string
  ): Promise<'replaced' | 'inserted'> {
    const item = Office.context.mailbox.item;
    if (!item || !('body' in item)) {
      throw new Error('Schreibzugriff nicht möglich.');
    }

    try {
      await new Promise<void>((resolve, reject) => {
        item.body.setAsync(
          text.replace(/\n/g, '<br>'),
          { coercionType: Office.CoercionType.Html },
          (result) => {
            if (result.status === Office.AsyncResultStatus.Succeeded) resolve();
            else reject(new Error('Ersetzen fehlgeschlagen.'));
          }
        );
      });
      return 'replaced';
    } catch {
      await this.insertText(text);
      return 'inserted';
    }
  }

  /**
   * Identifies the open mail's thread for loading earlier mails as reply
   * context: the conversation id (Read and Compose mode) and, in Read mode,
   * the sender's address as fallback when there is no conversation yet.
   */
  public getConversationContext(): {
    conversationId?: string;
    sender?: string;
  } {
    const item = Office.context.mailbox.item;
    if (!item) return {};
    const conversationId = item.conversationId || undefined;
    if (this.isComposeMode()) return { conversationId };
    const sender = (
      item as Office.MessageRead
    ).from?.emailAddress?.toLowerCase();
    return { conversationId, sender: sender || undefined };
  }

  /**
   * Returns the email addresses in To/Cc (minus the signed-in user's own
   * address), used to check everyone's calendar availability. Handles both
   * Read mode (synchronous arrays) and Compose mode (async Recipients).
   */
  public async getRecipients(): Promise<string[]> {
    const item = Office.context.mailbox.item;
    if (!item) return [];

    const ownAddress =
      Office.context.mailbox.userProfile?.emailAddress?.toLowerCase();

    const extractAddresses = (
      recipients: Office.EmailAddressDetails[]
    ): string[] =>
      recipients
        .map((r) => r.emailAddress?.toLowerCase())
        .filter(
          (address): address is string =>
            Boolean(address) && address !== ownAddress
        );

    let to: Office.EmailAddressDetails[];
    let cc: Office.EmailAddressDetails[];

    if (this.isComposeMode()) {
      const composeItem = item as Office.MessageCompose;
      [to, cc] = await Promise.all([
        this.getComposeRecipients(composeItem.to),
        this.getComposeRecipients(composeItem.cc),
      ]);
    } else {
      const readItem = item as Office.MessageRead;
      to = readItem.to ?? [];
      cc = readItem.cc ?? [];
    }

    return [...new Set([...extractAddresses(to), ...extractAddresses(cc)])];
  }

  /**
   * Builds a "Betreff/Von/An/Cc" header block for the currently open message,
   * since `getBodyText()` only returns the body - the current (outermost)
   * message's own sender/recipients/subject aren't part of it, only those of
   * older quoted messages further down. Without this, the AI has no way to
   * know who wrote/received the message it's summarizing. Read mode only:
   * in Compose mode there's no sent message yet to describe.
   */
  public getThreadHeader(): string {
    if (this.isComposeMode()) return '';
    const item = Office.context.mailbox.item as Office.MessageRead | undefined;
    if (!item) return '';

    const formatAddress = (r: Office.EmailAddressDetails) =>
      r.displayName ? `${r.displayName} <${r.emailAddress}>` : r.emailAddress;

    const lines = [
      item.subject && `Betreff: ${item.subject}`,
      item.from && `Von: ${formatAddress(item.from)}`,
      item.to?.length && `An: ${item.to.map(formatAddress).join(', ')}`,
      item.cc?.length && `Cc: ${item.cc.map(formatAddress).join(', ')}`,
    ].filter(Boolean);

    return lines.length > 0 ? `${lines.join('\n')}\n\n` : '';
  }

  /**
   * Counterpart and participants of the currently open message, used to
   * pre-fill the Outlook "new event" form. `counterpartName` is the first
   * name of the person the meeting is with - the sender in Read mode, the
   * first To recipient in Compose mode. Unlike `getRecipients()`,
   * `participants` also includes the sender in Read mode - when reading the
   * other person's mail, they are the one the meeting was agreed with, while
   * To only holds the user's own address. Kept out of `getRecipients()` on
   * purpose, since that feeds the availability check, which would otherwise
   * ask for every sender's calendar link.
   */
  public async getMeetingContext(): Promise<{
    counterpartName: string;
    participants: string[];
  }> {
    const item = Office.context.mailbox.item;
    if (!item) return { counterpartName: '', participants: [] };

    const ownAddress =
      Office.context.mailbox.userProfile?.emailAddress?.toLowerCase();
    const recipients = await this.getRecipients();

    let counterpart: Office.EmailAddressDetails | undefined;
    let sender: string | undefined;
    if (this.isComposeMode()) {
      const to = await this.getComposeRecipients(
        (item as Office.MessageCompose).to
      );
      counterpart = to.find(
        (r) => r.emailAddress?.toLowerCase() !== ownAddress
      );
    } else {
      const readItem = item as Office.MessageRead;
      counterpart = readItem.from;
      sender = readItem.from?.emailAddress?.toLowerCase();
    }

    const participants = [
      ...new Set([
        ...(sender && sender !== ownAddress ? [sender] : []),
        ...recipients,
      ]),
    ];
    return {
      counterpartName: firstName(counterpart?.displayName),
      participants,
    };
  }

  private async getComposeRecipients(
    recipients: Office.Recipients
  ): Promise<Office.EmailAddressDetails[]> {
    return new Promise((resolve) => {
      recipients.getAsync((result) => {
        if (result.status === Office.AsyncResultStatus.Succeeded) {
          resolve(result.value);
        } else {
          resolve([]);
        }
      });
    });
  }

  /**
   * Opens a URL in a new browser window/tab. `Office.context.ui.openBrowserWindow`
   * has no Read/Compose mode restriction, but per its requirement-set support
   * matrix it isn't implemented in Outlook on the web or new Outlook - only
   * classic desktop Outlook. `window.open` is the fallback for everywhere else.
   */
  public openUrl(url: string): void {
    try {
      const supportsOpenBrowserWindow =
        Office.context.requirements.isSetSupported(
          'OpenBrowserWindowApi',
          '1.1'
        );
      if (supportsOpenBrowserWindow) {
        Office.context.ui.openBrowserWindow(url);
      } else {
        window.open(url, '_blank');
      }
    } catch (error) {
      console.error('openUrl failed:', error);
      throw new Error('Kalender-Termin-Fenster konnte nicht geöffnet werden.');
    }
  }

  public isComposeMode(): boolean {
    const item = Office.context.mailbox.item;
    // Prüfe ob body.setSelectedDataAsync existiert ohne 'any' zu nutzen
    return (
      !!item &&
      'body' in item &&
      typeof (item.body as Office.Body).setSelectedDataAsync === 'function'
    );
  }

  public displayReply(text: string): void {
    Office.context.mailbox.item?.displayReplyAllForm(
      text.replace(/\n/g, '<br>')
    );
  }

  public showNotification(message: string): void {
    Office.context.mailbox.item?.notificationMessages.replaceAsync('inkai', {
      type: Office.MailboxEnums.ItemNotificationMessageType
        .InformationalMessage,
      message,
      icon: 'icon-16',
      persistent: false,
    });
  }
}

export const officeService = new OfficeService();
