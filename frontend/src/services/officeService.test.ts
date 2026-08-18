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

    new OfficeService().openUrl('https://outlook.office.com/calendar/0/deeplink/compose');

    expect(openBrowserWindowSpy).toHaveBeenCalledWith(
      'https://outlook.office.com/calendar/0/deeplink/compose'
    );
    expect(openSpy).not.toHaveBeenCalled();
  });

  it('falls back to window.open when the host does not support it (OWA/new Outlook)', () => {
    isSetSupportedSpy.mockReturnValue(false);

    new OfficeService().openUrl('https://outlook.office.com/calendar/0/deeplink/compose');

    expect(openSpy).toHaveBeenCalledWith(
      'https://outlook.office.com/calendar/0/deeplink/compose',
      '_blank'
    );
    expect(openBrowserWindowSpy).not.toHaveBeenCalled();
  });
});
