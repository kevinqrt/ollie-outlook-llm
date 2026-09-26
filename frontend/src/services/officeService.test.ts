import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { OfficeService } from './officeService';

describe('OfficeService.openUrl', () => {
  let openSpy: ReturnType<typeof vi.fn>;
  let openBrowserWindowSpy: ReturnType<typeof vi.fn>;
  let isSetSupportedSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    openSpy = vi.fn();
    openBrowserWindowSpy = vi.fn();
    isSetSupportedSpy = vi.fn();

    vi.stubGlobal('window', { open: openSpy });
    vi.stubGlobal('Office', {
      context: {
        requirements: { isSetSupported: isSetSupportedSpy },
        ui: { openBrowserWindow: openBrowserWindowSpy },
      },
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('uses openBrowserWindow when the host supports it (classic desktop Outlook)', () => {
    isSetSupportedSpy.mockReturnValue(true);

    new OfficeService().openUrl(
      'https://outlook.office.com/calendar/0/deeplink/compose'
    );

    expect(openBrowserWindowSpy).toHaveBeenCalledWith(
      'https://outlook.office.com/calendar/0/deeplink/compose'
    );
    expect(openSpy).not.toHaveBeenCalled();
  });

  it('falls back to window.open when the host does not support it (OWA/new Outlook)', () => {
    isSetSupportedSpy.mockReturnValue(false);

    new OfficeService().openUrl(
      'https://outlook.office.com/calendar/0/deeplink/compose'
    );

    expect(openSpy).toHaveBeenCalledWith(
      'https://outlook.office.com/calendar/0/deeplink/compose',
      '_blank'
    );
    expect(openBrowserWindowSpy).not.toHaveBeenCalled();
  });
});

describe('OfficeService.replaceInsertedText', () => {
  type BodyCallback = (result: { status: string; value?: string }) => void;

  function stubBody(options: { setAsyncSucceeds: boolean }) {
    const setAsync = vi.fn(
      (_html: string, _options: unknown, cb: BodyCallback) =>
        cb({ status: options.setAsyncSucceeds ? 'succeeded' : 'failed' })
    );
    const setSelectedDataAsync = vi.fn(
      (_html: string, _options: unknown, cb: BodyCallback) =>
        cb({ status: 'succeeded' })
    );
    vi.stubGlobal('Office', {
      AsyncResultStatus: { Succeeded: 'succeeded' },
      CoercionType: { Html: 'html', Text: 'text' },
      context: {
        mailbox: {
          item: { body: { setAsync, setSelectedDataAsync } },
        },
      },
    });
    return { setAsync, setSelectedDataAsync };
  }

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('replaces the whole draft with just the new reply - no old content kept', async () => {
    const { setAsync, setSelectedDataAsync } = stubBody({
      setAsyncSucceeds: true,
    });

    await expect(
      new OfficeService().replaceInsertedText('Neue Antwort\nZweite Zeile')
    ).resolves.toBe('replaced');

    expect(setAsync).toHaveBeenCalledWith(
      'Neue Antwort<br>Zweite Zeile',
      { coercionType: 'html' },
      expect.any(Function)
    );
    expect(setSelectedDataAsync).not.toHaveBeenCalled();
  });

  it('falls back to inserting at the cursor when the write itself fails', async () => {
    const { setAsync, setSelectedDataAsync } = stubBody({
      setAsyncSucceeds: false,
    });

    await expect(
      new OfficeService().replaceInsertedText('Neue Antwort')
    ).resolves.toBe('inserted');

    expect(setAsync).toHaveBeenCalled();
    expect(setSelectedDataAsync).toHaveBeenCalledWith(
      'Neue Antwort',
      { coercionType: 'html' },
      expect.any(Function)
    );
  });
});

describe('OfficeService.insertText', () => {
  type BodyCallback = (result: { status: string; value?: string }) => void;

  function stubBody() {
    const setSelectedDataAsync = vi.fn(
      (_text: string, _options: unknown, cb: BodyCallback) =>
        cb({ status: 'succeeded' })
    );
    vi.stubGlobal('Office', {
      AsyncResultStatus: { Succeeded: 'succeeded' },
      CoercionType: { Html: 'html', Text: 'text' },
      context: {
        mailbox: {
          item: { body: { setSelectedDataAsync } },
        },
      },
    });
    return { setSelectedDataAsync };
  }

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('inserts the reply as HTML at the cursor', async () => {
    const { setSelectedDataAsync } = stubBody();

    await new OfficeService().insertText('Zeile 1\nZeile 2');

    expect(setSelectedDataAsync).toHaveBeenCalledWith(
      'Zeile 1<br>Zeile 2',
      { coercionType: 'html' },
      expect.any(Function)
    );
  });
});

describe('OfficeService.getMeetingContext', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('includes the sender and To/Cc without the own address in Read mode', async () => {
    vi.stubGlobal('Office', {
      context: {
        mailbox: {
          userProfile: { emailAddress: 'Me@example.com' },
          item: {
            subject: 'AW: Ja, wir können uns treffen',
            from: {
              displayName: 'Sören Müller',
              emailAddress: 'Soeren@example.com',
            },
            to: [{ emailAddress: 'me@example.com' }],
            cc: [
              { emailAddress: 'alice@example.com' },
              { emailAddress: 'soeren@example.com' },
            ],
            body: {},
          },
        },
      },
    });

    const context = await new OfficeService().getMeetingContext();

    expect(context).toEqual({
      counterpartName: 'Sören',
      participants: ['soeren@example.com', 'alice@example.com'],
    });
  });

  it('takes the first name from "Nachname, Vorname" display names', async () => {
    vi.stubGlobal('Office', {
      context: {
        mailbox: {
          item: {
            from: {
              displayName: 'Müller, Sören',
              emailAddress: 'soeren@example.com',
            },
            body: {},
          },
        },
      },
    });

    const context = await new OfficeService().getMeetingContext();

    expect(context.counterpartName).toBe('Sören');
  });

  it('returns an empty context when no item is open', async () => {
    vi.stubGlobal('Office', { context: { mailbox: { item: undefined } } });

    expect(await new OfficeService().getMeetingContext()).toEqual({
      counterpartName: '',
      participants: [],
    });
  });
});

describe('OfficeService.getConversationContext', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('returns conversation id and lower-cased sender in Read mode', () => {
    vi.stubGlobal('Office', {
      context: {
        mailbox: {
          item: {
            conversationId: 'conv-1',
            from: { emailAddress: 'Max@Example.com' },
          },
        },
      },
    });

    expect(new OfficeService().getConversationContext()).toEqual({
      conversationId: 'conv-1',
      sender: 'max@example.com',
    });
  });

  it('returns only the conversation id in Compose mode', () => {
    vi.stubGlobal('Office', {
      context: {
        mailbox: {
          item: {
            conversationId: 'conv-1',
            body: { setSelectedDataAsync: vi.fn() },
          },
        },
      },
    });

    expect(new OfficeService().getConversationContext()).toEqual({
      conversationId: 'conv-1',
    });
  });

  it('returns nothing without an open item', () => {
    vi.stubGlobal('Office', { context: { mailbox: { item: null } } });

    expect(new OfficeService().getConversationContext()).toEqual({});
  });
});
