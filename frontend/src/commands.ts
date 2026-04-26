import { runReplyWorkflow } from './services/replyWorkflow';

/**
 * Ribbon-Button Entrypoint.
 */
async function generateAutoReplyDirect(event: Office.AddinCommands.Event) {
  try {
    await runReplyWorkflow();
  } catch (error) {
    console.error('Ollie: Ribbon Action failed', error);
  } finally {
    event.completed();
  }
}

Office.onReady((info) => {
  if (info.host === Office.HostType.Outlook) {
    Office.actions.associate(
      'generateAutoReplyDirect',
      generateAutoReplyDirect
    );
  }
});
