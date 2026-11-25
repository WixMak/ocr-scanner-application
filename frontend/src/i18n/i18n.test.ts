import { DEFAULT_LANGUAGE, detectInitialLanguage, resources, storeLanguage } from '.';

const LANGUAGE_STORAGE_KEY = 'ocr-form-scanner.language';

const mockBrowserLanguage = (language: string) =>
  jest.spyOn(navigator, 'language', 'get').mockReturnValue(language);

describe('language detection', () => {
  afterEach(() => window.localStorage.clear());

  it('prefers the language the user chose before', () => {
    mockBrowserLanguage('en-GB');
    storeLanguage('zh-CN');

    expect(detectInitialLanguage()).toBe('zh-CN');
  });

  it.each([
    ['zh-HK', 'zh-CN'],
    ['zh-CN', 'zh-CN'],
    ['fr-FR', DEFAULT_LANGUAGE],
  ])('uses the browser language %s when nothing was chosen', (browserLanguage, expected) => {
    mockBrowserLanguage(browserLanguage);

    expect(detectInitialLanguage()).toBe(expected);
  });

  it('ignores an unsupported stored language', () => {
    mockBrowserLanguage('en-US');
    window.localStorage.setItem(LANGUAGE_STORAGE_KEY, 'klingon');

    expect(detectInitialLanguage()).toBe(DEFAULT_LANGUAGE);
  });

  it('still works when storage is blocked', () => {
    mockBrowserLanguage('zh-TW');
    jest.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('SecurityError');
    });
    jest.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('SecurityError');
    });

    expect(() => storeLanguage('en')).not.toThrow();
    expect(detectInitialLanguage()).toBe('zh-CN');
  });

  it('has the same namespaces for every language', () => {
    expect(Object.keys(resources['zh-CN'])).toEqual(Object.keys(resources.en));
  });
});
