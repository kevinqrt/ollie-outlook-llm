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

  public async insertText(text: string): Promise<void> {
    return new Promise((resolve, reject) => {
      const item = Office.context.mailbox.item;
      if (!item || !('body' in item)) {
        return reject(new Error('Schreibzugriff nicht möglich.'));
      }

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
