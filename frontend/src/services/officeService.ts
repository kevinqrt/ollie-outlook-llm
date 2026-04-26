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

  public async hideNotification(): Promise<void> {
    return new Promise((resolve) => {
      const item = Office.context.mailbox.item;
      if (!item) return resolve();
      item.notificationMessages.removeAsync('inkai', () => resolve());
    });
  }
}

export const officeService = new OfficeService();
