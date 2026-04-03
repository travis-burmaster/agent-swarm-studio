import React, { useState } from "react";
import { replaceAgent, ReplaceResult } from "../lib/api";

interface ReplaceAgentModalProps {
  agentId: string;
  agentName: string;
  onClose: () => void;
  onReplaced: (result: ReplaceResult) => void;
}

export default function ReplaceAgentModal({
  agentId,
  agentName,
  onClose,
  onReplaced,
}: ReplaceAgentModalProps) {
  const [registryUrl, setRegistryUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ReplaceResult | null>(null);

  const handleReplace = async () => {
    const url = registryUrl.trim();
    if (!url || loading) return;
    setLoading(true);
    setError(null);
    try {
      const res = await replaceAgent(agentId, url);
      setResult(res);
      onReplaced(res);
    } catch (err: any) {
      const detail =
        err?.response?.data?.detail || err?.message || "Failed to replace agent";
      setError(detail);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-card border border-border rounded-xl w-full max-w-md p-6">
        <h2 className="text-white font-semibold text-sm mb-1">
          Replace Agent: <span className="text-indigo-400">{agentName}</span>
        </h2>
        <p className="text-muted text-xs mb-4">
          Slot: <code className="text-gray-400">{agentId}</code> — the current
          agent will be backed up and can be restored later.
        </p>

        {result ? (
          /* Success state */
          <div>
            <div className="bg-green-900/30 border border-green-700/50 rounded-lg p-3 mb-4">
              <p className="text-green-300 text-sm font-medium">
                Replaced with {result.new_name}
              </p>
              <p className="text-green-400/70 text-xs mt-1">
                Role: {result.new_role} — container is restarting
              </p>
            </div>
            <button
              onClick={onClose}
              className="w-full bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium py-2 rounded-lg transition-colors"
            >
              Done
            </button>
          </div>
        ) : (
          /* Input state */
          <div>
            <label className="text-xs text-muted block mb-1">
              gitagent Registry URL
            </label>
            <input
              type="text"
              value={registryUrl}
              onChange={(e) => setRegistryUrl(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleReplace();
              }}
              placeholder="e.g. shreyas-lyzr/quant-sim"
              className="w-full bg-black/40 border border-border rounded-lg px-3 py-2 text-sm text-white placeholder-muted focus:outline-none focus:border-indigo-500 transition-colors mb-3"
              disabled={loading}
              autoFocus
            />

            {error && (
              <div className="bg-red-900/30 border border-red-700/50 rounded-lg p-2 mb-3">
                <p className="text-red-300 text-xs">{error}</p>
              </div>
            )}

            <div className="flex gap-2">
              <button
                onClick={onClose}
                disabled={loading}
                className="flex-1 bg-gray-700 hover:bg-gray-600 disabled:opacity-50 text-white text-sm py-2 rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleReplace}
                disabled={loading || !registryUrl.trim()}
                className="flex-1 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium py-2 rounded-lg transition-colors flex items-center justify-center gap-2"
              >
                {loading ? (
                  <>
                    <span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Replacing...
                  </>
                ) : (
                  "Replace"
                )}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
