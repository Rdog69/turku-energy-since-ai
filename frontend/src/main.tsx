import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

import { loadPayload } from './lib/model'

const root = createRoot(document.getElementById('root')!)
loadPayload()
  .then(() => root.render(<StrictMode><App /></StrictMode>))
  .catch(() => root.render(
    <p style={{ padding: 32, fontSize: 16 }}>
      Forecast data not found. Run <code>python frontend/scripts/build_data.py</code> from the repository root, then reload.
    </p>,
  ))
