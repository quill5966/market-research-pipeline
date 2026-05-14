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

  const {
    productName,
    productContext,
    searchTerms,
    includeDomains,
    excludeDomains,
    maxResultsPerTerm,
    maxArticleChars,
    dedupTitleSimilarity,
    dedupSnippetSimilarity,
  } = formState;
  const setProductName = (v: string) => onFormChange({ ...formState, productName: v });
  const setProductContext = (v: string) => onFormChange({ ...formState, productContext: v });
  const setSearchTerms = (v: string[]) => onFormChange({ ...formState, searchTerms: v });
  const setIncludeDomains = (v: string[]) => onFormChange({ ...formState, includeDomains: v });
  const setExcludeDomains = (v: string[]) => onFormChange({ ...formState, excludeDomains: v });
  const setMaxResultsPerTerm = (v: string) => onFormChange({ ...formState, maxResultsPerTerm: v });
  const setMaxArticleChars = (v: string) => onFormChange({ ...formState, maxArticleChars: v });
  const setDedupTitleSimilarity = (v: string) => onFormChange({ ...formState, dedupTitleSimilarity: v });
  const setDedupSnippetSimilarity = (v: string) => onFormChange({ ...formState, dedupSnippetSimilarity: v });

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isValid =
    productName.trim().length >= 2 &&
    productContext.trim().length >= 10 &&
    searchTerms.length >= 1;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!isValid || isSubmitting) return;

    const parsedMaxResults = Number(maxResultsPerTerm);
    if (!Number.isInteger(parsedMaxResults) || parsedMaxResults < 1 || parsedMaxResults > 20) {
      setError('Max results per term must be an integer between 1 and 20.');
      setShowAdvanced(true);
      return;
    }
    const parsedMaxChars = Number(maxArticleChars);
    if (!Number.isInteger(parsedMaxChars) || parsedMaxChars < 500 || parsedMaxChars > 20000) {
      setError('Max article chars must be an integer between 500 and 20000.');
      setShowAdvanced(true);
      return;
    }
    const parsedTitleSim = Number(dedupTitleSimilarity);
    if (!Number.isFinite(parsedTitleSim) || parsedTitleSim < 0 || parsedTitleSim > 1) {
      setError('Dedup title similarity must be a number between 0 and 1.');
      setShowAdvanced(true);
      return;
    }
    const parsedSnippetSim = Number(dedupSnippetSimilarity);
    if (!Number.isFinite(parsedSnippetSim) || parsedSnippetSim < 0 || parsedSnippetSim > 1) {
      setError('Dedup snippet similarity must be a number between 0 and 1.');
      setShowAdvanced(true);
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const result = await createRun({
        product_name: productName.trim(),
        product_context: productContext.trim(),
        search_terms: searchTerms,
        include_domains: includeDomains,
        exclude_domains: excludeDomains,
        max_results_per_term: parsedMaxResults,
        max_article_chars: parsedMaxChars,
        dedup_title_similarity: parsedTitleSim,
        dedup_snippet_similarity: parsedSnippetSim,
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
              <span className="label-text">Product name</span>
            </div>
            <p className="field-help">
              Short label for your product or company. Used as the brief title.
            </p>
            <input
              id="product-name"
              className="field-input"
              type="text"
              value={productName}
              onChange={(e) => setProductName(e.target.value)}
              placeholder="e.g., Acme DB"
              maxLength={80}
            />
          </div>

          <div className="field">
            <div className="field-label">
              <span className="label-text">Product context</span>
              <span className="field-counter">
                {productContext.length} / 2000
              </span>
            </div>
            <p className="field-help">
              Mission, target customer, current roadmap bets, your PM role. The more
              specific this is, the sharper the next-step ideas will be.
            </p>
            <textarea
              id="product-context"
              className="field-textarea"
              value={productContext}
              onChange={(e) => setProductContext(e.target.value.slice(0, 2000))}
              placeholder={`e.g., Acme DB is a managed Postgres for fintech startups. Our wedge is row-level security and audit logging out of the box. Current bets: SOC 2 automation, multi-region replication. I PM the security and compliance workstream — buyer is the head of platform/infra at a Series A–C fintech.`}
              rows={6}
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

          {showAdvanced && (
            <div className="advanced-panel">
              <div className="field">
                <div className="field-label">
                  <span className="label-text">Max results per term</span>
                </div>
                <p className="field-help">
                  Tavily results requested per search term.
                </p>
                <input
                  type="number"
                  className="field-input"
                  min={1}
                  max={20}
                  step={1}
                  value={maxResultsPerTerm}
                  onChange={(e) => setMaxResultsPerTerm(e.target.value)}
                />
              </div>

              <div className="field">
                <div className="field-label">
                  <span className="label-text">Max article chars</span>
                </div>
                <p className="field-help">
                  Per-article content truncation before extraction.
                </p>
                <input
                  type="number"
                  className="field-input"
                  min={500}
                  max={20000}
                  step={500}
                  value={maxArticleChars}
                  onChange={(e) => setMaxArticleChars(e.target.value)}
                />
              </div>

              <div className="field">
                <div className="field-label">
                  <span className="label-text">Dedup title similarity</span>
                </div>
                <p className="field-help">
                  Jaccard threshold for clustering by title within a domain (0–1).
                </p>
                <input
                  type="number"
                  className="field-input"
                  min={0}
                  max={1}
                  step={0.05}
                  value={dedupTitleSimilarity}
                  onChange={(e) => setDedupTitleSimilarity(e.target.value)}
                />
              </div>

              <div className="field">
                <div className="field-label">
                  <span className="label-text">Dedup snippet similarity</span>
                </div>
                <p className="field-help">
                  Jaccard threshold for cross-domain snippet dedup (0–1).
                </p>
                <input
                  type="number"
                  className="field-input"
                  min={0}
                  max={1}
                  step={0.05}
                  value={dedupSnippetSimilarity}
                  onChange={(e) => setDedupSnippetSimilarity(e.target.value)}
                />
              </div>
            </div>
          )}

          <div className="form-footer">
            <button
              type="button"
              className="btn btn-text"
              onClick={() => setShowAdvanced((v) => !v)}
              aria-expanded={showAdvanced}
            >
              <i className={`ti ${showAdvanced ? 'ti-chevron-up' : 'ti-chevron-down'}`} />{' '}
              Advanced options
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
