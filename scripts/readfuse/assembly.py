"""Build one cumulative, honestly labeled learning edition."""
from pathlib import Path

from . import state as store


def labels(config):
    if config['target_language'].lower().split('-')[0] == 'id':
        return {'title': 'ReadFuse — Edisi pembelajaran', 'partial': 'Edisi sebagian', 'complete': 'Seluruh cakupan buku telah diproses',
                'missing': 'Belum diproses', 'partial_chapter': 'Bab sebagian', 'summary': 'Ringkasan bab',
                'note': 'Catatan ReadFuse — Penjelasan tambahan', 'pending': 'Komponen pembelajaran belum selesai',
                'warnings': 'Catatan pemeriksaan sumber', 'partial_summary': 'Ringkasan hanya untuk bagian yang sudah diproses'}
    return {'title': 'ReadFuse — Learning edition', 'partial': 'Partial edition', 'complete': 'All indexed book coverage processed',
            'missing': 'Not processed', 'partial_chapter': 'Partial chapter', 'summary': 'Chapter summary',
            'note': 'ReadFuse note — Additional explanation', 'pending': 'Learning components pending',
            'warnings': 'Source inspection warnings', 'partial_summary': 'Summary covers processed portions only'}


def render(job, state, report):
    if report['issues']:
        raise ValueError('Cannot assemble corrupt job: ' + '; '.join(report['issues']))
    if not state['selected']:
        raise ValueError('Select source coverage before assembly')
    lab = labels(state['config'])
    valid = set(report['valid']) - set(report['failed'])
    parts = [f'# {lab["title"]}', lab['complete'] if report['book_complete'] else lab['partial']]
    if not report.get('semantic_review_complete', False):
        parts.append('**Status review semantik:** belum semua bab terpilih memiliki review semantik terbaru.'
                     if state['config']['target_language'].lower().split('-')[0] == 'id'
                     else '**Semantic review status:** not all selected chapters have a current semantic review.')
    missing = [c['title'] for c in state['index']['chapters']
               if any(f'translation:{sid}' not in valid for sid in c['segment_ids'])]
    if state['config']['mode'] == 'summarize':
        missing = [c['title'] for c in state['index']['chapters'] if f'summary:{c["id"]}' not in valid]
    if missing:
        parts.append(f'**{lab["missing"]}:** ' + '; '.join(missing))
    if report['pending'] or report['failed']:
        parts.append(f'**{lab["pending"]}.**')
    if report['warnings']:
        parts.append('## ' + lab['warnings'] + '\n\n' + '\n'.join('- ' + w for w in report['warnings']))
    for chapter in state['index']['chapters']:
        cid = chapter['id']
        selected = store.chapter_ids(state, cid)
        if not selected:
            continue
        translated = [sid for sid in selected if f'translation:{sid}' in valid]
        if not translated and f'summary:{cid}' not in valid:
            continue
        heading = f'heading:{cid}'
        if heading in valid:
            title = store.safe_path(job, state['artifacts'][heading]['path']).read_text(encoding='utf-8').strip()
        else:
            title = chapter['title'] + (' (judul sumber; terjemahan belum tersedia)' if state['config']['target_language'].startswith('id') else ' (source title; translation pending)')
        parts.append('## ' + title)
        partial = len(selected) != len(chapter['segment_ids']) or (state['config']['mode'] != 'summarize' and translated != selected)
        if partial:
            parts.append('**' + lab['partial_chapter'] + '**')
        if state['config']['mode'] != 'summarize':
            # Show explicit gaps within a selected chapter, not just a global notice.
            for sid in chapter['segment_ids']:
                if sid not in translated:
                    parts.append('> ' + lab['missing'])
                    continue
                artifact = state['artifacts'][f'translation:{sid}']
                parts.append(store.safe_path(job, artifact['path']).read_text(encoding='utf-8').strip())
                key = f'notes:{sid}'
                if key in valid:
                    text = store.safe_path(job, state['artifacts'][key]['path']).read_text(encoding='utf-8')
                    for note in store.validate_notes(text, sid)['notes']:
                        parts.append('> **' + lab['note'] + '**\n>\n' + '\n'.join('> ' + line for line in note['text'].splitlines()))
        summary = f'summary:{cid}'
        if summary in valid and (state['config']['mode'] == 'summarize' or translated == selected):
            parts.append('### ' + lab['summary'])
            if partial:
                parts.append('*' + lab['partial_summary'] + '*')
            parts.append(store.safe_path(job, state['artifacts'][summary]['path']).read_text(encoding='utf-8').strip())
    return ('\n\n'.join(parts) + '\n').encode('utf-8')


def assemble(job: Path) -> Path:
    with store.job_lock(job):
        state = store.load_job(job)
        report = store.report(job, state)
        content = render(job, state, report)
        target = store.safe_path(job, 'edition/book.md')
        store.atomic_write(target, content)
        return target
