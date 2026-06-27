const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";

export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || DEFAULT_API_BASE_URL
).replace(/\/$/, "");

async function readApiResponse(response) {
  const text = await response.text();
  let payload = {};

  if (text) {
    try {
      payload = JSON.parse(text);
    } catch (error) {
      throw new Error(
        `Expected JSON from the backend, received: ${text.slice(0, 120)}`,
        { cause: error }
      );
    }
  }

  if (!response.ok) {
    throw new Error(payload.detail || `Backend request failed with ${response.status}`);
  }

  return payload;
}

export async function scanRepository(repoPath) {
  const response = await fetch(`${API_BASE_URL}/api/scan`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      repo_path: repoPath,
    }),
  });

  return readApiResponse(response);
}

export async function summarizeFile({ repoPath, fileId, provider }) {
  const response = await fetch(`${API_BASE_URL}/api/summarize`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      repo_path: repoPath,
      file_id: fileId,
      provider,
    }),
  });

  return readApiResponse(response);
}
