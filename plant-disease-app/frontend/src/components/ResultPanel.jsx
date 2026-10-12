export default function ResultPanel({ result }) {
  if (!result) return null

  return (
    <div style={{ marginTop: '1.5rem' }}>
      <h3>🐛 Pest Damage Diagnosis</h3>

      {result.mock_mode && (
        <p style={{ background: '#665500', padding: '0.5rem', borderRadius: 0 }}>
          ⚠️ Mock mode – model not loaded yet
        </p>
      )}

      <p><strong>Damage Type:</strong> {result.damage_display}</p>
      <p><strong>Severity:</strong> {result.severity}</p>

      <div className="confidence-bar">
        <div
          className="confidence-fill"
          style={{ width: `${result.confidence * 100}%` }}
        ></div>
      </div>
      <p>Confidence: {(result.confidence * 100).toFixed(1)}%</p>

      {result.likely_pests?.length > 0 && (
        <p><strong>🐜 Likely Pests:</strong> {result.likely_pests.join(', ')}</p>
      )}

      {result.treatment && (
        <div style={{ marginTop: '1rem' }}>
          <h4>💊 Treatment Plan</h4>
          <p><strong>🌿 Organic:</strong> {result.treatment.organic}</p>
          <p><strong>🧪 Chemical:</strong> {result.treatment.chemical}</p>
          <p><strong>🌱 Cultural:</strong> {result.treatment.cultural}</p>
          <p><strong>⏰ Urgency:</strong> {result.urgency}</p>
        </div>
      )}

      {result.top_predictions && (
        <details>
          <summary>🔍 Top 5 predictions</summary>
          <ul>
            {result.top_predictions.map((p, i) => (
              <li key={i}>
                {p.class}: {(p.confidence * 100).toFixed(1)}%
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  )
}