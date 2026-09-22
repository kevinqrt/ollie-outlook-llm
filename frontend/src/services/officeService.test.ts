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
