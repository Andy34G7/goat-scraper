"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area";
import { X, Download, Maximize2, ZoomIn, ZoomOut, PanelRightClose, FileText } from "lucide-react";

export interface PDFTab {
  id: string;
  url: string;
  title: string;
}

interface PDFViewerProps {
  tabs: PDFTab[];
  activeTabId: string | null;
  onTabChange: (id: string) => void;
  onTabClose: (id: string) => void;
  onClose: () => void;
}

export function PDFViewer({ tabs, activeTabId, onTabChange, onTabClose, onClose }: PDFViewerProps) {
  const [scale, setScale] = useState(100);

  const handleZoomIn = () => setScale((prev) => Math.min(prev + 25, 200));
  const handleZoomOut = () => setScale((prev) => Math.max(prev - 25, 50));

  if (tabs.length === 0) return null;

  const activeTab = tabs.find((t) => t.id === activeTabId) || tabs[0];

  return (
    <div className="fixed top-0 right-0 h-screen w-[55vw] max-w-4xl z-50 flex flex-col bg-white dark:bg-slate-900 border-l border-slate-200 dark:border-slate-700 shadow-2xl">
      {/* Tabs Bar */}
      <div className="flex items-center border-b border-slate-200 dark:border-slate-700 bg-slate-100 dark:bg-slate-800/80">
        <Button
          variant="ghost"
          size="icon"
          className="h-10 w-10 shrink-0 rounded-none border-r border-slate-200 dark:border-slate-700 hover:bg-slate-200 dark:hover:bg-slate-700"
          onClick={onClose}
        >
          <PanelRightClose className="h-4 w-4" />
        </Button>
        <ScrollArea className="flex-1">
          <div className="flex">
            {tabs.map((tab) => (
              <div
                key={tab.id}
                className={`group flex items-center gap-2 px-3 py-2 border-r border-slate-200 dark:border-slate-700 cursor-pointer min-w-0 max-w-[200px] ${tab.id === activeTab.id
                  ? "bg-white dark:bg-slate-900 text-slate-900 dark:text-white"
                  : "bg-slate-50 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700"
                  }`}
                onClick={() => onTabChange(tab.id)}
              >
                <FileText className="h-3.5 w-3.5 shrink-0 text-red-500" />
                <span className="text-xs truncate">{tab.title}</span>
                <button
                  className="ml-auto shrink-0 p-0.5 rounded hover:bg-slate-200 dark:hover:bg-slate-600 opacity-0 group-hover:opacity-100 transition-opacity"
                  onClick={(e) => {
                    e.stopPropagation();
                    onTabClose(tab.id);
                  }}
                >
                  <X className="h-3 w-3" />
                </button>
              </div>
            ))}
          </div>
          <ScrollBar orientation="horizontal" />
        </ScrollArea>
      </div>

      {/* Toolbar */}
      <div className="px-3 py-2 border-b border-slate-200 dark:border-slate-700 flex items-center justify-between shrink-0 bg-slate-50 dark:bg-slate-800/50">
        <span className="text-sm font-medium truncate text-slate-700 dark:text-slate-300">{activeTab.title}</span>
        <div className="flex items-center gap-1">
          <div className="flex items-center gap-0.5 bg-slate-200/80 dark:bg-slate-700/80 rounded-md px-1.5 py-1">
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6 hover:bg-slate-300 dark:hover:bg-slate-600"
              onClick={handleZoomOut}
              disabled={scale <= 50}
            >
              <ZoomOut className="h-3.5 w-3.5" />
            </Button>
            <span className="text-xs font-medium w-10 text-center">{scale}%</span>
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6 hover:bg-slate-300 dark:hover:bg-slate-600"
              onClick={handleZoomIn}
              disabled={scale >= 200}
            >
              <ZoomIn className="h-3.5 w-3.5" />
            </Button>
          </div>
          <a href={activeTab.url} target="_blank" rel="noopener noreferrer">
            <Button variant="ghost" size="icon" className="h-8 w-8 hover:bg-slate-200 dark:hover:bg-slate-700">
              <Maximize2 className="h-4 w-4" />
            </Button>
          </a>
          <a href={activeTab.url} download>
            <Button variant="ghost" size="icon" className="h-8 w-8 hover:bg-slate-200 dark:hover:bg-slate-700">
              <Download className="h-4 w-4" />
            </Button>
          </a>
        </div>
      </div>

      {/* PDF Content */}
      <div className="flex-1 overflow-x-auto overflow-y-hidden bg-slate-200 dark:bg-slate-950">
        <div
          className="h-full relative transition-[width] duration-200 ease-out"
          style={{
            width: `${scale}%`,
            margin: scale <= 100 ? '0 auto' : '0'
          }}
        >
          <iframe
            src={`${activeTab.url}#toolbar=0&navpanes=0&view=FitH`}
            className="w-full h-full border-0 bg-white"
            title={activeTab.title}
          />
        </div>
      </div>
    </div>
  );
}
