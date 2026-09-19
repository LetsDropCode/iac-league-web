"""Emit credential-free backup health to independently evaluated CloudWatch alarms."""
import json
import logging
import time


def backup_healthy(store, now=None, max_age=7200):
    now = time.time() if now is None else now
    try:
        status = json.loads(store.path('.backup-status.json').read_text())
        age = now - status['last_success']
        return status.get('verified') is True and 0 <= age < max_age
    except (OSError, ValueError, KeyError, TypeError):
        return False


def emit_health(store, client, service):
    healthy = backup_healthy(store)
    client.put_metric_data(Namespace='IACLeague/Storage', MetricData=[{
        'MetricName': 'BackupHealthy',
        'Dimensions': [{'Name': 'Service', 'Value': service}],
        'Value': int(healthy), 'Unit': 'Count',
    }])
    return healthy


def monitor_loop(store, client, service, stopped):
    # Runs separately from backup I/O: stalled backups eventually report stale health.
    # If this process/network dies, CloudWatch's missing-data alarm still evaluates.
    while not stopped.is_set():
        try:
            emit_health(store, client, service)
        except Exception as exc:
            # Do not log SDK exception details that could contain endpoints/credentials.
            logging.error('BACKUP_MONITOR_FAILED type=%s; CloudWatch must alarm on missing data', type(exc).__name__)
        stopped.wait(60)
