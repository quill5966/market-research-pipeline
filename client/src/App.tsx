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

export interface FormState {
  domain: string;
  searchTerms: string[];
  includeDomains: string[];
  excludeDomains: string[];
}

const EMPTY_FORM: FormState = {
  domain: '',
  searchTerms: [],
  includeDomains: [],
  excludeDomains: [],
};

export default function App() {
  const [formState, setFormState] = useState<FormState>(EMPTY_FORM);

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
