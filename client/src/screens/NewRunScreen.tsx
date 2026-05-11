/**
 * Screen 1: New Run — configuration form for starting a pipeline run.
 *
 * Form state is owned by App (survives in-app navigation).
 * Only isSubmitting and error are local to this screen.
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AppBar } from '../components/AppBar';
import { PillInput } from '../components/PillInput';
import { createRun } from '../api/client';
import type { FormState } from '../App';

interface NewRunScreenProps {
  formState: FormState;
  onFormChange: (state: FormState) => void;
}

export function NewRunScreen({ formState, onFormChange }: NewRunScreenProps) {
  const navigate = useNavigate();

  const { domain, searchTerms, includeDomains, excludeDomains } = formState;
  const setDomain = (v: string) => onFormChange({ ...formState, domain: v });
  const setSearchTerms = (v: string[]) => onFormChange({ ...formState, searchTerms: v });
  const setIncludeDomains = (v: string[]) => onFormChange({ ...formState, includeDomains: v });
  const setExcludeDomains = (v: string[]) => onFormChange({ ...formState, excludeDomains: v });

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isValid = domain.trim().length >= 10 && searchTerms.length >= 1;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!isValid || isSubmitting) return;

    setIsSubmitting(true);
    setError(null);

    try {
      const result = await createRun({
        domain_description: domain.trim(),
        search_terms: searchTerms,
        include_domains: includeDomains,
        exclude_domains: excludeDomains,
      });
      localStorage.setItem('lastRunId', result.id);
      navigate(`/runs/${result.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start run');
      setIsSubmitting(false);
    }
  }

  return (
    <>
      <AppBar />
      <div className="app-body">
        <form onSubmit={handleSubmit}>
          <div className="field">
            <div className="field-label">
              <span className="label-text">Domain description</span>
            </div>
            <p className="field-help">
              Describe the product domain you want to research. Be specific — this
              guides the AI's analysis and synthesis.
            </p>
            <textarea
              id="domain-description"
              className="field-textarea"
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              placeholder="e.g., Enterprise identity and access management (IAM)"
              rows={2}
            />
          </div>

          <div className="field">
            <div className="field-label">
              <span className="label-text">Search terms</span>
            </div>
            <p className="field-help">
              Enter search queries to find relevant news. Press Enter or comma to add.
            </p>
            <PillInput
              id="search-terms"
              values={searchTerms}
              onChange={setSearchTerms}
              placeholder="e.g., enterprise SSO market"
            />
          </div>

          <div className="field">
            <div className="field-label">
              <span className="label-text">
                Include domains <span className="optional">optional</span>
              </span>
              <button
                type="button"
                className="btn-clear-all"
                onClick={() => setIncludeDomains([])}
                disabled={includeDomains.length === 0}
              >
                Clear all
              </button>
            </div>
            <p className="field-help">
              Limit search to these domains. Leave empty to search all sources.
            </p>
            <PillInput
              id="include-domains"
              values={includeDomains}
              onChange={setIncludeDomains}
              placeholder="e.g., reuters.com"
            />
          </div>

          <div className="field">
            <div className="field-label">
              <span className="label-text">
                Exclude domains <span className="optional">optional</span>
              </span>
              <button
                type="button"
                className="btn-clear-all"
                onClick={() => setExcludeDomains([])}
                disabled={excludeDomains.length === 0}
              >
                Clear all
              </button>
            </div>
            <p className="field-help">
              Exclude these domains from search results.
            </p>
            <PillInput
              id="exclude-domains"
              values={excludeDomains}
              onChange={setExcludeDomains}
              placeholder="e.g., medium.com"
            />
          </div>

          <div className="form-footer">
            <button
              type="button"
              className="btn btn-text"
              disabled
              title="Coming soon"
            >
              <i className="ti ti-settings" /> Advanced options
            </button>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={!isValid || isSubmitting}
            >
              {isSubmitting ? (
                <>
                  <i className="ti ti-loader-2" style={{ animation: 'spin 1s linear infinite' }} />
                  Starting…
                </>
              ) : (
                <>
                  <i className="ti ti-player-play" /> Run research
                </>
              )}
            </button>
          </div>

          {error && (
            <div className="info-notice" style={{ marginTop: 16, borderLeft: '3px solid #b91c1c' }}>
              <i className="ti ti-alert-circle" />
              {error}
            </div>
          )}
        </form>
      </div>
    </>
  );
}
