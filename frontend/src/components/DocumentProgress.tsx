import { useState, useEffect } from 'react';
import { type DocumentStatus } from '../lib/utils';

export function DocumentProgress({ status }: { status: DocumentStatus }) {
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    if (status === 'indexing') {
      const interval = setInterval(() => {
        setProgress((prev) => {
          if (prev < 20) return prev + 2.5;
          if (prev < 50) return prev + 1.5;
          if (prev < 80) return prev + 0.8;
          if (prev < 95) return prev + 0.2;
          return prev;
        });
      }, 200);
      return () => clearInterval(interval);
    }
  }, [status]);

  if (status !== 'indexing') return null;

  let stageLabel = 'Initializing...';
  if (progress < 15) {
    stageLabel = 'Uploading document...';
  } else if (progress < 40) {
    stageLabel = 'Parsing & segmenting PDF...';
  } else if (progress < 75) {
    stageLabel = 'Extracting graph entities...';
  } else if (progress < 95) {
    stageLabel = 'Embedding & indexing chunks...';
  } else {
    stageLabel = 'Finalizing writes...';
  }

  return (
    <div className="mt-2 w-full space-y-1">
      <div className="w-full bg-[#eae3d2] rounded-full h-1.5 overflow-hidden">
        <div
          className="bg-amber-500 h-full transition-all duration-300 ease-out animate-pulse"
          style={{ width: `${progress}%` }}
        />
      </div>
      <div className="flex justify-between text-[9px] font-bold text-[#8c7e6b] tracking-tight">
        <span>{stageLabel}</span>
        <span>{Math.round(progress)}%</span>
      </div>
    </div>
  );
}
