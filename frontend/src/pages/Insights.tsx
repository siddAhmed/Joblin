import { useState, useEffect, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { insightsApi, type Citation } from "@/api/insights";
import type { Match } from "@/api/matches";

export function Insights() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [progress, setProgress] = useState<string | null>(null);
  const [done, setDone] = useState<{ analyzed: number; skipped: number } | null>(null);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [expandedSkill, setExpandedSkill] = useState<string | null>(null);
  const [citations, setCitations] = useState<Citation[]>([]);
  const [loadingCitations, setLoadingCitations] = useState(false);
  const isAnalyzing = useRef(false);
  const qc = useQueryClient();

  const { data: skillsData = { skills: [], total_jobs_analyzed: 0 }, refetch: refetchSkills } = useQuery({
    queryKey: ["insights-skills"],
    queryFn: insightsApi.skills,
  });

  useEffect(() => {
    const analyzeParam = searchParams.get("analyze");
    if (!analyzeParam || isAnalyzing.current) return;
    const matchIds = analyzeParam.split(",").map(Number).filter(Boolean);
    if (matchIds.length === 0) return;
    isAnalyzing.current = true;
    runAnalysis(matchIds);
  }, []);

  async function runAnalysis(matchIds: number[]) {
    const cachedMatches = qc.getQueryData<Match[]>(["matches", ""]) ?? [];
    const matchMap = new Map(cachedMatches.map((m) => [m.id, m]));

    let totalAnalyzed = 0;
    let totalSkipped = 0;

    for (let i = 0; i < matchIds.length; i++) {
      const matchId = matchIds[i];
      const match = matchMap.get(matchId);
      const label = match
        ? `${match.job_title} at ${match.company_name}`
        : `job #${matchId}`;

      setProgress(`Analyzing ${i + 1} of ${matchIds.length}: ${label}`);

      try {
        const result = await insightsApi.analyze([matchId]);
        totalAnalyzed += result.analyzed;
        totalSkipped += result.skipped;
        await refetchSkills();
      } catch {
        setAnalysisError(`Failed on: ${label}`);
      }
    }

    setProgress(null);
    setDone({ analyzed: totalAnalyzed, skipped: totalSkipped });
    setSearchParams({}, { replace: true });
    isAnalyzing.current = false;
  }

  async function toggleCitations(skillName: string) {
    if (expandedSkill === skillName) {
      setExpandedSkill(null);
      setCitations([]);
      return;
    }
    setLoadingCitations(true);
    try {
      const data = await insightsApi.citations(skillName);
      setCitations(data);
      setExpandedSkill(skillName);
    } finally {
      setLoadingCitations(false);
    }
  }

  const { skills, total_jobs_analyzed } = skillsData;

  return (
    <div className="max-w-2xl">
      {(progress || done || analysisError) && (
        <div className="mb-5 p-3 bg-[#111] border border-[#1e1e1e] rounded text-xs space-y-1">
          {progress && <div className="text-[#888]">{progress}</div>}
          {analysisError && <div className="text-red-400">{analysisError}</div>}
          {done && (
            <div className="text-emerald-500">
              Done - analyzed {done.analyzed}, skipped {done.skipped} already processed
            </div>
          )}
        </div>
      )}

      <div className="flex items-center justify-between mb-4">
        <div className="text-xs text-[#555]">
          {skills.length} skills tracked across {total_jobs_analyzed} job{total_jobs_analyzed !== 1 ? "s" : ""}
        </div>
      </div>

      {skills.length === 0 && !progress && (
        <p className="text-sm text-[#555]">
          No skills yet. Select matches on the Matches page and click "Analyze skills".
        </p>
      )}

      <div className="space-y-0.5">
        {skills.map((skill, i) => (
          <div key={skill.name}>
            <div className="flex items-center gap-3 px-3 py-2 rounded hover:bg-[#111]">
              <span className="text-[10px] text-[#444] w-5 text-right">{i + 1}</span>
              <span className="flex-1 text-sm text-[#e5e5e5]">{skill.name}</span>
              <button
                onClick={() => toggleCitations(skill.name)}
                className={`text-xs font-mono px-2 py-0.5 rounded border ${
                  expandedSkill === skill.name
                    ? "border-[#4e9eff] text-[#4e9eff] bg-[#0e2040]"
                    : "border-[#2a2a2a] text-[#666] hover:text-[#ccc]"
                }`}
              >
                {skill.count}
              </button>
            </div>
            {expandedSkill === skill.name && (
              <div className="ml-8 mb-1 px-3 py-2 bg-[#0a0a0a] border border-[#1e1e1e] rounded text-xs">
                {loadingCitations ? (
                  <span className="text-[#555]">Loading...</span>
                ) : citations.length === 0 ? (
                  <span className="text-[#555]">No citations found.</span>
                ) : (
                  <ul className="space-y-0.5">
                    {citations.map((c, j) => (
                      <li key={j} className="text-[#888]">
                        {c.company_name} <span className="text-[#555]">- {c.job_title}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
