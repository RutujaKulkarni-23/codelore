export interface SavedCase {
  id: string;
  title: string;
  question: string;
  agent?: string;
  answer?: string;
  citations?: Array<{ path: string; start: number; end: number }>;
  timestamp: number;
}

const STORAGE_KEY = "codelore_recent_cases";

export function getRecentCases(): SavedCase[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function getCaseById(id: string): SavedCase | undefined {
  const cases = getRecentCases();
  return cases.find((c) => c.id === id);
}

export function saveRecentCase(caseItem: SavedCase): void {
  try {
    const current = getRecentCases();
    const filtered = current.filter((c) => c.id !== caseItem.id);
    const updated = [caseItem, ...filtered].slice(0, 20);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
  } catch {
    // Graceful fallback if storage quota exceeded or disabled
  }
}
