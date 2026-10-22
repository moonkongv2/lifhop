"""Explicit source-selected GitHub worker; optional polling, no installed daemon."""
import argparse
import os
import shutil
import time
from datetime import timedelta
from functools import partial
from pathlib import Path
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.db import engine
from app.acquisition.common import ProbeError
from app.collectors.bundle import private_write, read_json
from app.collectors.client import bundle_lock
from app.collectors.github import GitHubConfig, Preparation, validate_bundle
from app.collectors.github_reader import RepositoryReader, Paused
from app.models.collection_job import CollectionSubscription, CollectionJob
from app.schemas.collection_run import GitHubRunCreate, GitHubCollectorItem
from app.services import collection_jobs as jobs
from app.services.collection_runs import create_batch, ingest_batch_item, finish_batch, save_receipt, now


def cleanup_spool(bind, root, user_id, subscription_id, *, clock=None):
    """Caller holds the spool lock. Retain failed/recoverable work indefinitely."""
    clock = clock or now()
    for directory in root.glob("job-*"):
        if not directory.is_dir() or directory.is_symlink():
            raise ProbeError("Invalid job directory")
        identity_path = directory / "identity.json"
        if not identity_path.exists():
            continue
        identity = read_json(identity_path, 65536)
        if identity.get("owner") != user_id or identity.get("subscription") != subscription_id or identity.get("database") != bind.url.render_as_string(hide_password=True):
            raise ProbeError("Spool belongs to another database/source/job")
        with Session(bind) as db:
            jobs.subscription(db, user_id, subscription_id)
            job = db.get(CollectionJob, identity.get("job"))
            if (job is None or directory.name != f"job-{job.id}" or job.subscription_id != subscription_id or
                    job.status not in {"completed", "empty", "partial", "cancelled"} or
                    job.finished_at is None or job.finished_at > clock - timedelta(days=7)):
                continue
            if any(p.is_symlink() for p in directory.rglob("*")):
                raise ProbeError("Symlink spool files are not allowed")
            shutil.rmtree(directory)


def run_once(bind, subscription_id, spool, *, token=None, reader_factory=RepositoryReader):
    worker_id = str(uuid4())
    with Session(bind) as db:
        sub = db.get(CollectionSubscription, subscription_id)
        if sub is None:
            raise ProbeError("Unknown subscription")
        if sub.provider != 'github':
            raise ProbeError('Use the source-bound Codex agent for this subscription')
        user_id, config = sub.user_id, sub.config
        result = jobs.claim(db, user_id, subscription_id, worker_id)
        mode = db.get(CollectionJob, result[0]).mode if result else None
        db.commit()
    if result is None:
        return False
    job_id, generation = result
    cfg = GitHubConfig.model_validate(config)

    def guard(db):
        return jobs.leased(db, user_id, subscription_id, job_id, worker_id, generation)

    def heartbeat():
        with Session(bind) as db:
            guard(db)
            db.commit()

    try:
        # One private, source-local spool lock also bounds aggregate spool growth.
        root = Path(spool).absolute()
        if root.is_symlink() or any(p.is_symlink() for p in root.parents):
            raise ProbeError("Symlink spool directories are not allowed")
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        root.chmod(0o700)
        with bundle_lock(root):
            cleanup_spool(bind, root, user_id, subscription_id)
            paths = list(root.rglob("*"))
            if any(p.is_symlink() for p in paths):
                raise ProbeError("Symlink spool files are not allowed")
            if sum(p.stat().st_size for p in paths if p.is_file()) > 512 * 1024 * 1024 - 9 * 1024 * 1024:
                raise Paused("SPOOL_QUOTA")
            directory = root / f"job-{job_id}"
            directory.mkdir(mode=0o700, exist_ok=True)
            if directory.is_symlink():
                raise ProbeError("Symlink job directory is not allowed")
            identity = dict(owner=user_id, subscription=subscription_id, job=job_id,
                database=bind.url.render_as_string(hide_password=True))
            identity_path = directory / "identity.json"
            if not identity_path.exists():
                if any(directory.iterdir()):
                    raise ProbeError("Unbound spool directory; use a fresh private spool")
                private_write(identity_path, identity)
            elif read_json(identity_path, 65536) != identity:
                raise ProbeError("Spool belongs to another database/source/job")
            cfg_path = directory / "config.json"
            if not cfg_path.exists():
                private_write(cfg_path, config)
            elif read_json(cfg_path, 65536) != config:
                raise ProbeError("Spool configuration changed")
            reader = reader_factory(directory / "cache", cfg, token=token)
            original_get = reader.get

            def bounded_get(*args, **kwargs):
                heartbeat()
                paths = list(root.rglob("*"))
                if any(p.is_symlink() for p in paths):
                    raise ProbeError("Symlink spool files are not allowed")
                if sum(p.stat().st_size for p in paths if p.is_file()) > 512 * 1024 * 1024 - 9 * 1024 * 1024:
                    raise Paused("SPOOL_QUOTA")
                result = original_get(*args, **kwargs)
                heartbeat()
                return result

            reader.get = bounded_get
            from app.collectors import github_incremental
            incremental = mode == "incremental"
            validator = github_incremental.validate_bundle if incremental else validate_bundle
            if not (directory / "manifest.json").exists():
                if incremental:
                    with Session(bind) as db:
                        current, _ = guard(db)
                        prep = github_incremental.Preparation(directory, cfg, reader, bind, current)
                        db.commit()
                else:
                    prep = Preparation(directory, cfg, reader)
                try:
                    prep.run()
                except Paused as error:
                    prep.state["retry_at"] = error.retry_at
                    prep.save()
                    raise
                heartbeat()
                prep.seal()
            manifest = validator(directory, cfg)
            fields = ("client_run_uuid", "provider", "scope", "manifest_digest", "parser_version",
                      "filter_version", "expected_items", "coverage")
            with Session(bind) as db:
                _, job = guard(db)
                batch = create_batch(db, user_id, GitHubRunCreate.model_validate(
                    {key: manifest[key] for key in fields}), job_id=job_id)
                job.run_id = batch.id
                run_id = batch.id
                db.commit()
            # Entry/version and receipt commit together. An uncertain ACK replays this frozen batch.
            for row in manifest["items"]:
                item = GitHubCollectorItem.model_validate(read_json(directory / row["file"], cfg.turn_bytes)) if row["file"] else None
                with Session(bind) as db:
                    guard(db)
                    if item:
                        ingest_batch_item(db, user_id, run_id, item, job_id=job_id)
                    else:
                        from app.models.collection_run import CollectionRun
                        save_receipt(db, db.get(CollectionRun, run_id), row["external_id"],
                            row["payload_digest"], "failed", "INVALID_ITEM")
                    db.commit()
            with Session(bind) as db:
                sub, job = guard(db)
                batch = finish_batch(db, user_id, run_id, job_id=job_id)
                job.status, job.finished_at = batch.status, now()
                job.error_code, job.retry_at = None, None
                sub.last_checked_at = now()
                if batch.status in {"completed", "empty"}:
                    if incremental:
                        github_incremental.advance(db, sub, manifest)
                    sub.last_success_at = now()
                else:
                    jobs.pause_schedule(sub, "PARTIAL_COLLECTION")
                db.commit()
    except (ProbeError, HTTPException, OSError, ValueError, KeyError, TypeError) as error:
        with Session(bind) as db:
            try:
                sub, job = guard(db)
            except HTTPException:
                return True  # Cancellation/takeover wins; never publish a stale result.
            jobs.fail_attempt(db, sub, job, error)
            db.commit()
    return True


def poll_once(bind, subscription_id, spool, **kwargs):
    with Session(bind) as db:
        sub = db.get(CollectionSubscription, subscription_id)
        if sub is None:
            raise ProbeError("Unknown subscription")
        jobs.schedule_due(db, sub.user_id, sub.id)
        db.commit()
    return run_once(bind, subscription_id, spool, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subscription-id", type=int, required=True)
    parser.add_argument("--spool", type=Path, required=True)
    parser.add_argument("--synthetic", action="store_true", help="Use only the fixed fictional example/repo fixture; no GitHub requests")
    parser.add_argument("--synthetic-revision", type=int, choices=(1, 2), help="Select fictional provider changes (requires --synthetic)")
    parser.add_argument("--poll-seconds", type=int, help="Poll this subscription every 1–60 seconds until stopped")
    parser.add_argument("--max-cycles", type=int, help="Stop polling after this many ticks (default: until Ctrl-C)")
    args = parser.parse_args()
    if args.synthetic_revision is not None and not args.synthetic:
        parser.error("--synthetic-revision requires --synthetic")
    if args.poll_seconds is not None and not 1 <= args.poll_seconds <= 60:
        parser.error("--poll-seconds must be between 1 and 60")
    if args.max_cycles is not None and (args.poll_seconds is None or args.max_cycles < 1):
        parser.error("--max-cycles requires polling and must be positive")
    # Runtime secret only: never a CLI argument, config file, DB field or log output.
    from app.collectors.github_fixture import SyntheticGitHubReader
    cycles = 0
    try:
        while True:
            action = poll_once if args.poll_seconds else run_once
            action(engine, args.subscription_id, args.spool,
                token=None if args.synthetic else os.environ.get("LIFHOP_GITHUB_TOKEN"),
                reader_factory=partial(SyntheticGitHubReader, revision=args.synthetic_revision or 1) if args.synthetic else RepositoryReader)
            cycles += 1
            if not args.poll_seconds or (args.max_cycles and cycles >= args.max_cycles):
                break
            time.sleep(args.poll_seconds)
    except KeyboardInterrupt:
        pass  # A running job's durable lease expires; restart with the same spool.


if __name__ == "__main__":
    main()
