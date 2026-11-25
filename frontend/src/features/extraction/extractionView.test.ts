import { extractionResult } from '../../test/fixtures';
import { buildExtractionJson, countByStatus, toFieldViews } from './extractionView';

describe('extractionView', () => {
  it('uses original values and statuses when nothing is edited', () => {
    const views = toFieldViews(extractionResult, {});

    expect(views.map((view) => [view.displayValue, view.displayStatus])).toEqual([
      ['陈大文', 'confirmed'],
      ['9123 4567', 'review'],
      ['', 'empty'],
    ]);
  });

  it('marks changed values as edited but ignores edits that match the original', () => {
    const views = toFieldViews(extractionResult, {
      'field-phone': '9123 4568',
      'field-name': '陈大文',
    });

    expect(views[0]?.displayStatus).toBe('confirmed');
    expect(views[1]).toMatchObject({ displayValue: '9123 4568', displayStatus: 'edited' });
  });

  it('builds JSON with values keyed by field key and per-field status', () => {
    const views = toFieldViews(extractionResult, { 'field-signed': '2026-11-20' });

    const json = buildExtractionJson(extractionResult, views);

    expect(json.values).toEqual({
      full_name: '陈大文',
      phone: '9123 4567',
      signed_date: '2026-11-20',
    });
    expect(json.fields[2]).toEqual({
      key: 'signed_date',
      label: '',
      value: '2026-11-20',
      status: 'edited',
      confidence: 1,
    });
  });

  it('counts fields by status', () => {
    expect(countByStatus(extractionResult.fields)).toEqual({ confirmed: 1, review: 1, empty: 1 });
  });
});
