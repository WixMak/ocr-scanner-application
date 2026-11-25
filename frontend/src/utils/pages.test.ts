import { groupByPage, pageAt } from './pages';

describe('pageAt', () => {
  it('returns the page at the index', () => {
    expect(pageAt(['first', 'second'], 1)).toBe('second');
  });

  it('refuses a page that does not exist', () => {
    expect(() => pageAt(['first'], 1)).toThrow(RangeError);
  });
});

describe('groupByPage', () => {
  it('groups items by page in page order and leaves out pages without items', () => {
    const items = [
      { id: 'c', pageIndex: 2 },
      { id: 'a', pageIndex: 0 },
      { id: 'b', pageIndex: 2 },
    ];

    expect(groupByPage(items, 3)).toEqual([
      { pageIndex: 0, items: [{ id: 'a', pageIndex: 0 }] },
      {
        pageIndex: 2,
        items: [
          { id: 'c', pageIndex: 2 },
          { id: 'b', pageIndex: 2 },
        ],
      },
    ]);
  });
});
