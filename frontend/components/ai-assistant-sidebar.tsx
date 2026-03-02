"use client";

import { useState, useEffect, useRef } from "react";
import { useChat } from "@ai-sdk/react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import {
  X,
  Send,
  Paperclip,
  Settings,
  MessageSquare,
  Bot,
  User,
  Loader2,
  FileText,
  Trash2,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubTrigger,
  DropdownMenuSubContent,
  DropdownMenuPortal,
} from "@/components/ui/dropdown-menu";
import { useStudyCart } from "@/components/study-cart-provider";

// We'll import the extractor we created
import { extractTextFromPdfUrl, extractTextFromFile } from "@/lib/pdf-extract";

interface AiAssistantSidebarProps {
  onClose: () => void;
  activeFileTitle?: string;
  activeFileUrl?: string;
}

export function AiAssistantSidebar({
  onClose,
  activeFileTitle,
  activeFileUrl,
}: AiAssistantSidebarProps) {
  const [view, setView] = useState<"chat" | "settings">("chat");

  // Settings state
  const [provider, setProvider] = useState<"openai" | "anthropic" | "google" | "ollama">("google");
  const [apiKey, setApiKey] = useState("");
  const [savedSettings, setSavedSettings] = useState({ provider: "google", apiKey: "" });

  // Context loading state
  const [isExtractingContext, setIsExtractingContext] = useState(false);
  const [activeFileContext, setActiveFileContext] = useState<string | null>(null);
  const [attachedFilesContext, setAttachedFilesContext] = useState<{ name: string, content: string }[]>([]);

  const { items: studyQueueItems } = useStudyCart();

  const handleSelectFromQueue = async (url: string, title: string) => {
    try {
      setIsExtractingContext(true);
      const text = await extractTextFromPdfUrl(url);
      setAttachedFilesContext(prev => [...prev, { name: title, content: text }]);
    } catch (err) {
      console.error(err);
      alert("Failed to extract context from the study queue pdf.");
    } finally {
      setIsExtractingContext(false);
    }
  };

  // Load settings on mount
  useEffect(() => {
    const savedProvider = localStorage.getItem("ai-provider");
    const savedKey = localStorage.getItem("ai-api-key");
    if (savedProvider) setProvider(savedProvider as any);
    if (savedKey) setApiKey(savedKey);
    setSavedSettings({
      provider: savedProvider || "google",
      apiKey: savedKey || ""
    });
  }, []);

  const handleSaveSettings = () => {
    localStorage.setItem("ai-provider", provider);
    localStorage.setItem("ai-api-key", apiKey);
    setSavedSettings({ provider, apiKey });
    alert("Settings saved successfully!");
  };

  const [input, setInput] = useState("");

  const transport = useRef<any>(null);
  useEffect(() => {
    // Dynamic import to avoid SSR issues if any, though it should be fine.
    // Actually just use DefaultChatTransport from ai.
  }, []);

  const {
    messages,
    sendMessage,
    status,
    error,
    setMessages,
  } = useChat({
    transport: new (require("ai").DefaultChatTransport)({ api: "/api/chat" }),
    onError: (error: any) => {
      console.error(error);
      alert(error.message || "An error occurred fetching the response");
    },
  });

  const isLoading = status === "streaming" || status === "submitted";

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setInput(e.target.value);
  };

  // Automatically extract context when the active file changes
  useEffect(() => {
    async function fetchContext() {
      if (!activeFileUrl) {
        setActiveFileContext(null);
        return;
      }

      setIsExtractingContext(true);
      try {
        const text = await extractTextFromPdfUrl(activeFileUrl);
        setActiveFileContext(text);
      } catch (err) {
        console.error("Error reading file context:", err);
        setActiveFileContext(null);
      } finally {
        setIsExtractingContext(false);
      }
    }

    fetchContext();
  }, [activeFileUrl]);

  // File Upload Handler
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      try {
        const text = await extractTextFromFile(file);
        setAttachedFilesContext(prev => [...prev, { name: file.name, content: text }]);
      } catch (err) {
        console.error(`Failed to parse attached file ${file.name}`, err);
        alert(`Could not read ${file.name}`);
      }
    }

    // Reset file input
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const removeAttachment = (indexToRemove: number) => {
    setAttachedFilesContext(prev => prev.filter((_, idx) => idx !== indexToRemove));
  };


  // Custom submit handler to inject context silently if needed
  const onSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    if (!savedSettings.apiKey && savedSettings.provider !== "ollama") {
      alert("Please configure and save your API Key in the Settings tab first.");
      setView("settings");
      return;
    }

    let fullPrompt = input;

    const contextFragments = [];
    if (activeFileTitle && activeFileContext) {
      contextFragments.push(`--- Active Document: ${activeFileTitle} ---\n${activeFileContext}`);
    }

    for (const attachment of attachedFilesContext) {
      contextFragments.push(`--- Attached Document: ${attachment.name} ---\n${attachment.content}`);
    }

    const context = contextFragments.length > 0 ? contextFragments.join('\n\n') : undefined;

    sendMessage(
      { text: input },
      {
        body: {
          provider: savedSettings.provider,
          apiKey: savedSettings.apiKey,
          ...(context ? { context } : {})
        }
      }
    );
    setInput("");
  };

  return (
    <div className="w-full flex flex-col h-full bg-white dark:bg-slate-900 shadow-xl overflow-hidden">
      {/* Header */}
      <div className="flex flex-col border-b border-slate-200 dark:border-slate-800 shrink-0">
        <div className="flex items-center justify-between p-3">
          <div className="flex items-center gap-2 text-indigo-600 dark:text-indigo-400">
            <Bot className="h-5 w-5" />
            <h2 className="font-semibold text-slate-900 dark:text-white">AI Assistant</h2>
          </div>
          <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>

        {/* View Tabs */}
        <div className="flex px-3 gap-2 pb-2">
          <Button
            variant={view === "chat" ? "secondary" : "ghost"}
            size="sm"
            className="flex-1 rounded-full text-xs h-7"
            onClick={() => setView("chat")}
          >
            <MessageSquare className="h-3 w-3 mr-1.5" />
            Chat
          </Button>
          <Button
            variant={view === "settings" ? "secondary" : "ghost"}
            size="sm"
            className="flex-1 rounded-full text-xs h-7"
            onClick={() => setView("settings")}
          >
            <Settings className="h-3 w-3 mr-1.5" />
            Settings
          </Button>
        </div>
      </div>

      {view === "settings" && (
        <ScrollArea className="flex-1 p-4">
          <div className="space-y-6">
            <div>
              <h3 className="text-sm font-medium mb-3">AI Provider</h3>
              <div className="flex flex-wrap gap-2 mb-2">
                {["google", "openai", "anthropic", "ollama"].map((p) => (
                  <Button
                    key={p}
                    variant={provider === p ? "default" : "outline"}
                    size="sm"
                    className="flex-1 capitalize text-xs h-8 min-w-[80px]"
                    onClick={() => setProvider(p as any)}
                  >
                    {p}
                  </Button>
                ))}
              </div>
            </div>

            <div>
              <h3 className="text-sm font-medium mb-2">
                {provider === "ollama" ? "Ollama Target URL (Optional)" : "API Key"}
              </h3>
              <p className="text-xs text-slate-500 mb-2">
                Stored locally in your browser. Never sent to our servers.
              </p>
              <div className="flex gap-2">
                <Input
                  type={provider === "ollama" ? "text" : "password"}
                  placeholder={provider === "ollama" ? "http://localhost:11434/api (Default)" : `Enter ${provider} API Key`}
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  className="text-xs flex-1"
                />
                <Button
                  size="sm"
                  onClick={handleSaveSettings}
                  className="bg-indigo-600 hover:bg-indigo-700 text-white"
                >
                  Save
                </Button>
              </div>
            </div>

            <div className="bg-amber-50 dark:bg-amber-950/30 p-3 rounded-lg border border-amber-200 dark:border-amber-800/50">
              <p className="text-[11px] text-amber-800 dark:text-amber-300">
                To use the AI Assistant, you must provide your own API key for the selected provider. The assistant will read your active PDF and any attached files to answer questions.
              </p>
            </div>
          </div>
        </ScrollArea>
      )}

      {view === "chat" && (
        <>
          {/* Chat Messages */}
          <ScrollArea className="flex-1 p-4">
            {messages.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center text-slate-500 space-y-3 mt-10">
                <div className="h-12 w-12 rounded-full bg-indigo-100 dark:bg-indigo-900/50 flex items-center justify-center">
                  <Bot className="h-6 w-6 text-indigo-600 dark:text-indigo-400" />
                </div>
                <div>
                  <p className="text-sm font-medium text-slate-900 dark:text-slate-100">
                    How can I help you study?
                  </p>
                  <p className="text-xs mt-1 max-w-[200px] mx-auto">
                    I can summarize the current document or answer specific questions about it.
                  </p>
                </div>
              </div>
            ) : (
              <div className="space-y-4 pb-4">
                {messages.map((message) => (
                  <div
                    key={message.id}
                    className={`flex gap-3 ${message.role === "user" ? "flex-row-reverse" : ""
                      }`}
                  >
                    <div
                      className={`h-6 w-6 shrink-0 rounded-full flex items-center justify-center ${message.role === "user"
                        ? "bg-slate-200 dark:bg-slate-700"
                        : "bg-indigo-100 dark:bg-indigo-900/50"
                        }`}
                    >
                      {message.role === "user" ? (
                        <User className="h-3.5 w-3.5 text-slate-600 dark:text-slate-300" />
                      ) : (
                        <Bot className="h-3.5 w-3.5 text-indigo-600 dark:text-indigo-400" />
                      )}
                    </div>
                    <div
                      className={`flex flex-col max-w-[85%] ${message.role === "user" ? "items-end" : "items-start"
                        }`}
                    >
                      <div
                        className={`px-3 py-2 rounded-2xl text-sm ${message.role === "user"
                          ? "bg-indigo-600 text-white rounded-tr-sm"
                          : "bg-slate-100 dark:bg-slate-800 text-slate-900 dark:text-slate-100 rounded-tl-sm border border-slate-200 dark:border-slate-700"
                          }`}
                      >
                        {message.role === "user" ? (
                          <p className="whitespace-pre-wrap">{message.parts?.map(p => p.type === 'text' ? (p as any).text : '').join('') || ""}</p>
                        ) : (
                          <div className="prose prose-sm dark:prose-invert max-w-none prose-p:leading-relaxed prose-pre:bg-slate-900 dark:prose-pre:bg-black prose-pre:p-2 prose-pre:rounded-md">
                            <ReactMarkdown
                              remarkPlugins={[remarkGfm, remarkMath]}
                              rehypePlugins={[rehypeKatex]}
                            >
                              {message.parts?.map(p => p.type === 'text' ? (p as any).text : '').join('') || ""}
                            </ReactMarkdown>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
                {isLoading && messages[messages.length - 1]?.role === "user" && (
                  <div className="flex gap-3">
                    <div className="h-6 w-6 shrink-0 rounded-full flex items-center justify-center bg-indigo-100 dark:bg-indigo-900/50">
                      <Bot className="h-3.5 w-3.5 text-indigo-600 dark:text-indigo-400" />
                    </div>
                    <div className="px-3 py-2 rounded-2xl bg-slate-100 dark:bg-slate-800 text-slate-900 dark:text-slate-100 rounded-tl-sm border border-slate-200 dark:border-slate-700 flex items-center gap-2">
                      <Loader2 className="h-3.5 w-3.5 animate-spin text-slate-500" />
                      <span className="text-xs text-slate-500">Thinking...</span>
                    </div>
                  </div>
                )}
              </div>
            )}
          </ScrollArea>

          {/* Context Indicators / Attachments */}
          <div className="px-3 pt-2 pb-1 border-t border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/50 shrink-0">
            <div className="flex flex-wrap gap-1">
              {activeFileTitle && (
                <Badge variant="secondary" className="text-[10px] px-1.5 py-0 h-5 font-normal flex items-center gap-1 bg-white dark:bg-slate-800 border-indigo-200 dark:border-indigo-800 text-indigo-700 dark:text-indigo-300">
                  {isExtractingContext ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <FileText className="h-3 w-3" />
                  )}
                  <span className="truncate max-w-[120px]">{activeFileTitle}</span>
                </Badge>
              )}

              {attachedFilesContext.map((file, idx) => (
                <Badge key={idx} variant="outline" className="text-[10px] px-1.5 py-0 h-5 font-normal flex items-center gap-1 bg-white dark:bg-slate-800 group">
                  <Paperclip className="h-3 w-3 text-slate-400" />
                  <span className="truncate max-w-[80px]">{file.name}</span>
                  <X
                    className="h-3 w-3 ml-0.5 text-slate-400 opacity-50 cursor-pointer hover:opacity-100"
                    onClick={() => removeAttachment(idx)}
                  />
                </Badge>
              ))}
            </div>
          </div>

          {/* Input Area */}
          <div className="p-3 bg-white dark:bg-slate-900 shrink-0">
            <form onSubmit={onSubmit} className="flex gap-2">
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileUpload}
                multiple
                className="hidden"
                accept=".pdf,.txt,.md,.csv,.js,.jsx,.ts,.tsx,.json,.mdx"
              />
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    className="shrink-0 h-9 w-9 border-slate-200 dark:border-slate-700"
                    title="Attach Files"
                  >
                    <Paperclip className="h-4 w-4 text-slate-500" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="start" className="w-56">
                  <DropdownMenuItem onClick={() => fileInputRef.current?.click()}>
                    Upload from Computer
                  </DropdownMenuItem>
                  {studyQueueItems.length > 0 && (
                    <>
                      <DropdownMenuSeparator />
                      <DropdownMenuSub>
                        <DropdownMenuSubTrigger>Select from Study Queue</DropdownMenuSubTrigger>
                        <DropdownMenuPortal>
                          <DropdownMenuSubContent>
                            {studyQueueItems.map(item => (
                              <DropdownMenuItem key={item.id} onClick={() => handleSelectFromQueue(item.url, item.title)}>
                                <span className="truncate max-w-[200px]">{item.title}</span>
                              </DropdownMenuItem>
                            ))}
                          </DropdownMenuSubContent>
                        </DropdownMenuPortal>
                      </DropdownMenuSub>
                    </>
                  )}
                </DropdownMenuContent>
              </DropdownMenu>
              <Input
                value={input}
                onChange={handleInputChange}
                placeholder="Ask about your documents..."
                className="flex-1 text-sm bg-slate-50 dark:bg-slate-800/50 border-slate-200 dark:border-slate-700"
                disabled={isLoading}
              />
              <Button
                type="submit"
                size="icon"
                disabled={isLoading || !input.trim()}
                className="shrink-0 h-9 w-9 bg-indigo-600 hover:bg-indigo-700 text-white"
              >
                <Send className="h-4 w-4" />
              </Button>
            </form>
          </div>
        </>
      )}
    </div>
  );
}
