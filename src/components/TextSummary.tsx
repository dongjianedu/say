import React from 'react';
import { IoClose } from 'react-icons/io5';

interface TextSummaryProps {
  summary: string | null;
  isLoading: boolean;
  onClose: () => void;
}

export default function TextSummary({
  summary,
  isLoading,
  onClose,
}: TextSummaryProps) {
  if (!isLoading && !summary) return null;

  return (
    <div className="mt-4 p-4 bg-gray-100 rounded-lg relative">
      <div className="flex justify-between items-start mb-2">
        <h3 className="text-lg font-semibold">AI 摘要</h3>
        <button
          onClick={onClose}
          className="text-gray-600 hover:text-gray-800"
        >
          <IoClose size={20} />
        </button>
      </div>

      {isLoading && !summary && (
        <div className="flex items-center gap-2 text-gray-600">
          <svg
            className="animate-spin h-5 w-5"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
          <span>正在生成摘要...</span>
        </div>
      )}

      {summary && (
        <div className="prose max-w-none">
          <p className="text-gray-700 whitespace-pre-wrap">
            {summary}
            {isLoading && (
              <span className="inline-block w-2 h-5 bg-blue-500 ml-0.5 animate-pulse" />
            )}
          </p>
        </div>
      )}
    </div>
  );
}
