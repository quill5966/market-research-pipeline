/**
 * Screen 2: Pipeline — polls run status and shows stage progress.
 * Auto-navigates to brief screen on completion.
 */

import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { AppBar } from '../components/AppBar';
import { PipelineStageList } from '../components/PipelineStageList';
import { getRun } from '../api/client';
import type { Run } from '../types/models';

export function PipelineScreen() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [run, setRun] = useState<Run | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;

    // Store in localStorage so refresh doesn't lose the run
    localStorage.setItem('lastRunId', id);

    let cancelled = false;

    async function poll() {
      try {
        const data = await getRun(id!);
        if (cancelled) return;
        setRun(data);

        if (data.status === 'complete') {
          navigate(`/runs/${id}/brief`, { replace: true });
          return;
        }

        if (data.status === 'failed') {
          return; // Stop polling, show error state
        }

        // Continue polling
        setTimeout(poll, 1500);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : 'Failed to fetch run');
      }
    }

    poll();

    return () => { cancelled = true; };
  }, [id, navigate]);

  function handleCancel() {
    navigate('/');
  }

  return (
    <>
      <AppBar
        actions={
          <button className="btn btn-ghost" onClick={handleCancel}>
            <i className="ti ti-arrow-left" /> Back
          </button>
        }
      />
      <div className="app-body">
        {error && (
          <div className="info-notice" style={{ borderLeft: '3px solid #b91c1c' }}>
            <i className="ti ti-alert-circle" />
            {error}
          </div>
        )}

        {run && (
          <>
            <div className="running-header">
              <h1 className="running-title">{run.request.product_name}</h1>
              <div className="running-meta">
                {run.request.search_terms.length} search terms · Claude Sonnet 4.6
              </div>
            </div>

            <PipelineStageList stages={run.stages} />

            {run.status === 'failed' && run.error && (
              <div
                className="info-notice"
                style={{ marginTop: 20, borderLeft: '3px solid #b91c1c' }}
              >
                <i className="ti ti-alert-circle" />
                Pipeline failed: {run.error}
              </div>
            )}

            {run.status !== 'failed' && (
              <div className="info-notice">
                <i className="ti ti-info-circle" />
                You can leave this page — the pipeline will continue running.
              </div>
            )}
          </>
        )}

        {!run && !error && (
          <div className="running-header">
            <h1 className="running-title">Loading…</h1>
          </div>
        )}
      </div>
    </>
  );
}
