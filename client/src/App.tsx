/**
 * App — root component with client-side routing.
 *
 * Form state is lifted here so it survives in-app navigation
 * (e.g. Back from pipeline screen) but clears on full page
 * reload (navigating away from the site entirely).
 */

import { useState } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { NewRunScreen } from './screens/NewRunScreen';
import { PipelineScreen } from './screens/PipelineScreen';
import { BriefScreen } from './screens/BriefScreen';
import {
  DEFAULT_INCLUDE_DOMAINS,
  DEFAULT_EXCLUDE_DOMAINS,
  DEFAULT_MAX_RESULTS_PER_TERM,
  DEFAULT_MAX_ARTICLE_CHARS,
  DEFAULT_DEDUP_TITLE_SIMILARITY,
  DEFAULT_DEDUP_SNIPPET_SIMILARITY,
} from './constants';

export interface FormState {
  domain: string;
  searchTerms: string[];
  includeDomains: string[];
  excludeDomains: string[];
  maxResultsPerTerm: string;
  maxArticleChars: string;
  dedupTitleSimilarity: string;
  dedupSnippetSimilarity: string;
}

const INITIAL_FORM: FormState = {
  domain: '',
  searchTerms: [],
  includeDomains: DEFAULT_INCLUDE_DOMAINS,
  excludeDomains: DEFAULT_EXCLUDE_DOMAINS,
  maxResultsPerTerm: String(DEFAULT_MAX_RESULTS_PER_TERM),
  maxArticleChars: String(DEFAULT_MAX_ARTICLE_CHARS),
  dedupTitleSimilarity: String(DEFAULT_DEDUP_TITLE_SIMILARITY),
  dedupSnippetSimilarity: String(DEFAULT_DEDUP_SNIPPET_SIMILARITY),
};

export default function App() {
  const [formState, setFormState] = useState<FormState>(INITIAL_FORM);

  return (
    <BrowserRouter>
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
    </BrowserRouter>
  );
}
