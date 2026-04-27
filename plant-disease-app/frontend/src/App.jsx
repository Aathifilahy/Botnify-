import { useState } from 'react'
import ImageUploader from './components/ImageUploader'
import HistoryPanel from './components/HistoryPanel'

function App() {
  const [activeTab, setActiveTab] = useState('upload')
  const [refreshHistory, setRefreshHistory] = useState(0)

  const handleScanComplete = () => {
    setRefreshHistory(prev => prev + 1)
    setActiveTab('history')
  }

  return (
    <div className="container">
      <h1>🌿 Leaf Disease Identifier</h1>
      <p>Upload a leaf photo — AI diagnoses the disease and suggests treatment</p>
      
      <div className="tabs">
        <button className={`tab-btn ${activeTab === 'upload' ? 'active' : ''}`} onClick={() => setActiveTab('upload')}>
          📸 Upload & Diagnose
        </button>
        <button className={`tab-btn ${activeTab === 'history' ? 'active' : ''}`} onClick={() => setActiveTab('history')}>
          🗂️ Scan History
        </button>
      </div>

      {activeTab === 'upload' && <ImageUploader onScanComplete={handleScanComplete} />}
      {activeTab === 'history' && <HistoryPanel key={refreshHistory} />}
    </div>
  )
}

export default App