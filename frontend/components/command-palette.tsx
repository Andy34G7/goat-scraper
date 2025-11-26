"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command";
import {
  BookOpen,
  FileText,
  Layers,
  Search,
  Home,
  Download,
} from "lucide-react";

interface SearchItem {
  type: "course" | "unit" | "file";
  title: string;
  subtitle?: string;
  href: string;
  download?: boolean;
}

interface CommandPaletteProps {
  items: SearchItem[];
}

export function CommandPalette({ items }: CommandPaletteProps) {
  const [open, setOpen] = React.useState(false);
  const router = useRouter();

  React.useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((open) => !open);
      }
    };

    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, []);

  const handleSelect = (item: SearchItem) => {
    setOpen(false);
    if (item.download) {
      window.open(item.href, "_blank");
    } else {
      router.push(item.href);
    }
  };

  const courses = items.filter((i) => i.type === "course");
  const units = items.filter((i) => i.type === "unit");
  const files = items.filter((i) => i.type === "file");

  const getIcon = (type: string) => {
    switch (type) {
      case "course":
        return <BookOpen className="mr-2 h-4 w-4" />;
      case "unit":
        return <Layers className="mr-2 h-4 w-4" />;
      case "file":
        return <FileText className="mr-2 h-4 w-4" />;
      default:
        return <Search className="mr-2 h-4 w-4" />;
    }
  };

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-1.5 text-sm text-slate-500 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors"
      >
        <Search className="h-4 w-4" />
        <span className="hidden sm:inline">Search...</span>
        <kbd className="pointer-events-none hidden h-5 select-none items-center gap-1 rounded border bg-slate-100 dark:bg-slate-700 px-1.5 font-mono text-[10px] font-medium sm:flex">
          <span className="text-xs">⌘</span>K
        </kbd>
      </button>
      <CommandDialog open={open} onOpenChange={setOpen}>
        <CommandInput placeholder="Search courses, units, files..." />
        <CommandList>
          <CommandEmpty>No results found.</CommandEmpty>
          
          <CommandGroup heading="Navigation">
            <CommandItem onSelect={() => { setOpen(false); router.push("/"); }}>
              <Home className="mr-2 h-4 w-4" />
              <span>Home</span>
            </CommandItem>
          </CommandGroup>

          {courses.length > 0 && (
            <>
              <CommandSeparator />
              <CommandGroup heading="Courses">
                {courses.map((item, i) => (
                  <CommandItem key={`course-${i}`} onSelect={() => handleSelect(item)}>
                    {getIcon(item.type)}
                    <span>{item.title}</span>
                    {item.subtitle && (
                      <span className="ml-2 text-xs text-slate-500">{item.subtitle}</span>
                    )}
                  </CommandItem>
                ))}
              </CommandGroup>
            </>
          )}

          {units.length > 0 && (
            <>
              <CommandSeparator />
              <CommandGroup heading="Units">
                {units.map((item, i) => (
                  <CommandItem key={`unit-${i}`} onSelect={() => handleSelect(item)}>
                    {getIcon(item.type)}
                    <span>{item.title}</span>
                    {item.subtitle && (
                      <span className="ml-2 text-xs text-slate-500">{item.subtitle}</span>
                    )}
                  </CommandItem>
                ))}
              </CommandGroup>
            </>
          )}

          {files.length > 0 && (
            <>
              <CommandSeparator />
              <CommandGroup heading="Files">
                {files.slice(0, 20).map((item, i) => (
                  <CommandItem key={`file-${i}`} onSelect={() => handleSelect(item)}>
                    {getIcon(item.type)}
                    <span className="truncate">{item.title}</span>
                    {item.subtitle && (
                      <span className="ml-2 text-xs text-slate-500 truncate">{item.subtitle}</span>
                    )}
                    <Download className="ml-auto h-3 w-3 text-slate-400" />
                  </CommandItem>
                ))}
                {files.length > 20 && (
                  <CommandItem disabled>
                    <span className="text-slate-500">...and {files.length - 20} more files</span>
                  </CommandItem>
                )}
              </CommandGroup>
            </>
          )}
        </CommandList>
      </CommandDialog>
    </>
  );
}
