/**
 * App — root component with client-side routing.
 *
 * Form state is lifted here so it survives in-app navigation
 * (e.g. Back from pipeline screen) but clears on full page
 * reload (navigating away from the site entirely).
 */

import { createContext, useState } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { NewRunScreen } from './screens/NewRunScreen';
import { PipelineScreen } from './screens/PipelineScreen';
import { BriefScreen } from './screens/BriefScreen';
import { PasscodeGate } from './components/PasscodeGate';
import {
  DEFAULT_INCLUDE_DOMAINS,
  DEFAULT_EXCLUDE_DOMAINS,
  DEFAULT_MAX_RESULTS_PER_TERM,
  DEFAULT_MAX_ARTICLE_CHARS,
  DEFAULT_DEDUP_TITLE_SIMILARITY,
  DEFAULT_DEDUP_SNIPPET_SIMILARITY,
} from './constants';
import type { RunRequest } from './types/models';

export interface FormState {
  productName: string;
  productContext: string;
  searchTerms: string[];
  includeDomains: string[];
  excludeDomains: string[];
  maxResultsPerTerm: string;
  maxArticleChars: string;
  dedupTitleSimilarity: string;
  dedupSnippetSimilarity: string;
}

const INITIAL_FORM: FormState = {
  productName: '',
  productContext: '',
  searchTerms: [],
  includeDomains: DEFAULT_INCLUDE_DOMAINS,
  excludeDomains: DEFAULT_EXCLUDE_DOMAINS,
  maxResultsPerTerm: String(DEFAULT_MAX_RESULTS_PER_TERM),
  maxArticleChars: String(DEFAULT_MAX_ARTICLE_CHARS),
  dedupTitleSimilarity: String(DEFAULT_DEDUP_TITLE_SIMILARITY),
  dedupSnippetSimilarity: String(DEFAULT_DEDUP_SNIPPET_SIMILARITY),
};

// Maps a completed run's RunRequest back to FormState for Re-Run prefill.
// Merges over INITIAL_FORM so newly-added FormState fields fall back to defaults.
export function mapRunRequestToFormState(req: RunRequest): FormState {
  return {
    ...INITIAL_FORM,
    productName: req.product_name,
    productContext: req.product_context,
    searchTerms: req.search_terms,
    includeDomains: req.include_domains ?? [],
    excludeDomains: req.exclude_domains ?? [],
    maxResultsPerTerm: String(req.max_results_per_term),
    maxArticleChars: String(req.max_article_chars),
    dedupTitleSimilarity: String(req.dedup_title_similarity),
    dedupSnippetSimilarity: String(req.dedup_snippet_similarity),
  };
}

export const FormStateContext = createContext<{
  setFormState: (s: FormState) => void;
}>({ setFormState: () => {} });

export default function App() {
  const [formState, setFormState] = useState<FormState>(INITIAL_FORM);

  return (
    <PasscodeGate>
      <BrowserRouter>
        <FormStateContext.Provider value={{ setFormState }}>
          <Routes>
            <Route
              path="/"
              element={
                <NewRunScreen
                  formState={formState}
                  onFormChange={setFormState}
                />
              }
            />
            <Route path="/runs/:id" element={<PipelineScreen />} />
            <Route path="/runs/:id/brief" element={<BriefScreen />} />
          </Routes>
        </FormStateContext.Provider>
      </BrowserRouter>
    </PasscodeGate>
  );
}
