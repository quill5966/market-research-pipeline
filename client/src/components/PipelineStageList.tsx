/**
 * PipelineStageList — renders the five pipeline stages with status icons.
 */

import type { Stage } from '../types/models';

const STAGE_LABELS: Record<string, string> = {
  search: 'Search',
  dedup: 'Deduplicate',
  group: 'Group by story',
  extract: 'Extract notes',
  synthesize: 'Synthesize brief',
  review: 'Agent review brief',
};

function formatElapsed(ms: number | null): string {
  if (ms === null) return '';
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function StepIcon({ status }: { status: string }) {
  if (status === 'done') {
    return (
      <div className="step-icon done">
        <i className="ti ti-check" />
      </div>
    );
  }
  if (status === 'active') {
    return (
      <div className="step-icon active">
        <i className="ti ti-loader-2" />
      </div>
    );
  }
  if (status === 'failed') {
    return (
      <div className="step-icon done" style={{ color: '#b91c1c' }}>
        <i className="ti ti-x" />
      </div>
    );
  }
  return (
    <div className="step-icon pending">
      <i className="ti ti-circle" />
    </div>
  );
}

interface PipelineStageListProps {
  stages: Stage[];
}

export function PipelineStageList({ stages }: PipelineStageListProps) {
  return (
    <ul className="pipeline-list">
      {stages.map((stage) => (
        <li
          key={stage.name}
          className={`pipeline-step${stage.status === 'active' ? ' is-active' : ''}`}
        >
          <StepIcon status={stage.status} />
          <div className="step-body">
            <div className="step-title">{STAGE_LABELS[stage.name] || stage.name}</div>
            <div className="step-detail">{stage.detail}</div>
          </div>
          {stage.elapsed_ms !== null && (
            <div className="step-time">{formatElapsed(stage.elapsed_ms)}</div>
          )}
        </li>
      ))}
    </ul>
  );
}
