export type PageGroup<Item> = {
  pageIndex: number;
  items: Item[];
};

export const pageAt = <Page>(pages: readonly Page[], pageIndex: number): Page => {
  const page = pages[pageIndex];
  if (page === undefined) {
    throw new RangeError(`Page ${pageIndex} does not exist.`);
  }
  return page;
};

export const groupByPage = <Item extends { pageIndex: number }>(
  items: readonly Item[],
  pageCount: number,
): PageGroup<Item>[] =>
  Array.from({ length: pageCount }, (_, pageIndex) => ({
    pageIndex,
    items: items.filter((item) => item.pageIndex === pageIndex),
  })).filter((group) => group.items.length > 0);
