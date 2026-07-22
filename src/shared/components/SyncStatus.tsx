export type SyncState = 'idle' | 'saving' | 'saved' | 'offline';

export function SyncStatus({ state }: { state: SyncState }) {
  const labels: Record<SyncState, string> = {
    idle: 'Local', saving: 'Saving…', saved: 'Synced', offline: 'Offline',
  };
  return <div className={`sync-status ${state}`} title="Reader data sync status">
    <i /> <span>{labels[state]}</span>
  </div>;
}
