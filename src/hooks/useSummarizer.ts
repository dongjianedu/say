import { useState, useCallback } from 'react';
import Constants from '../utils/Constants';

export const useSummarizer = () => {
  const [isLoading, setIsLoading] = useState(false);
  const [summary, setSummary] = useState<string | null>(null);

  const summarize = useCallback(async (text: string) => {
    setIsLoading(true);
    setSummary('');

    const templateName = text.length < 1000 ? 'chat' : 'interview_summary';

    try {
      const response = await fetch(Constants.SUMMARIZE_STREAM_API_URL, {
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

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('Response body is not readable');
      }

      const decoder = new TextDecoder();
      let fullText = '';
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.error) {
                throw new Error(data.error);
              }
              if (data.token) {
                fullText += data.token;
                setSummary(fullText);
              }
              if (data.done) {
                break;
              }
            } catch (parseError) {
              console.warn('Failed to parse SSE data:', parseError);
            }
          }
        }
      }
    } catch (error) {
      console.error('Summarization error:', error);
      alert(`摘要失败: ${error instanceof Error ? error.message : '未知错误'}`);
      setSummary(null);
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
