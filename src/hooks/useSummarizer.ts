import { useState, useCallback } from 'react';
import Constants from '../utils/Constants';

export const useSummarizer = () => {
  const [isLoading, setIsLoading] = useState(false);
  const [summary, setSummary] = useState<string | null>(null);

  const summarize = useCallback(async (text: string) => {
    setIsLoading(true);
    setSummary(null);

    const templateName = text.length < 1000 ? 'chat' : 'interview_summary';

    try {
      const response = await fetch(Constants.SUMMARIZE_API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text,
          template_name: templateName,
          max_tokens: 4096,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const result = await response.json();
      setSummary(result.summary);
    } catch (error) {
      console.error('Summarization error:', error);
      alert(`摘要失败: ${error instanceof Error ? error.message : '未知错误'}`);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const clearSummary = useCallback(() => {
    setSummary(null);
  }, []);

  return {
    isLoading,
    summary,
    summarize,
    clearSummary,
  };
};
