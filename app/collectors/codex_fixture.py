"""Fictional local Codex observations; never starts Codex or reads its home."""
from uuid import uuid4
from app.acquisition.common import ProbeError
from app.collectors.bundle import canonical_turn, digest, private_write, FILTER, FORMAT, PARSER


def prepare(source, directory, offset, revision):
    if '/synthetic/project' not in source.include_cwd and 'synthetic-thread' not in source.threads:
        raise ProbeError('Synthetic agent requires /synthetic/project or synthetic-thread selection')
    cfg = source.collector_config()
    directory.mkdir(mode=0o700)
    rows = []
    turns = [dict(id='turn-1', status='completed', startedAt=1767225600, completedAt=1767225610, items=[
        dict(id='user-1', type='userMessage', content=[dict(type='text', text='[Synthetic] Resume the selected project')]),
        dict(id='answer-1', type='agentMessage', phase='final_answer', text='[Synthetic] Initial recorded result')])]
    if revision == 2:
        turns.append(dict(id='turn-2', status='completed', startedAt=1767225620, completedAt=1767225630, items=[
            dict(id='user-2', type='userMessage', content=[dict(type='text', text='[Synthetic] What changed next?')]),
            dict(id='answer-2', type='agentMessage', phase='final_answer', text='[Synthetic] Appended turn on the old thread')]))
    from app.collectors.codex_agent import selected_rows
    selected = bool(selected_rows([dict(id='synthetic-thread', cwd='/synthetic/project')], source))
    for turn in turns if selected else []:
        item = canonical_turn(dict(id='synthetic-thread', name='[Synthetic] Local collection'), turn, cfg,
            archived=False, cwd='/synthetic/project')
        data = item.model_dump(mode='json')
        filename = f'item-{len(rows):06d}.json'
        private_write(directory/filename, data)
        rows.append(dict(external_id=item.external_id, payload_digest=digest(data), file=filename, error_code=None))
    manifest = dict(bundle_format=FORMAT, client_run_uuid=str(uuid4()), provider='codex', scope=f'mac:{cfg.device_uuid}',
        parser_version=PARSER, filter_version=FILTER, config_digest=digest(cfg.model_dump(mode='json')), items=rows,
        expected_items=len(rows), coverage=dict(discovered=1, selected=int(selected), excluded=int(not selected),
            read=int(selected), failed=0, deferred=0, gaps=[]))
    manifest['manifest_digest'] = digest(manifest)
    private_write(directory/'manifest.json', manifest)
    return manifest, 0
