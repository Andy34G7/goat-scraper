"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import React, { useEffect, useRef, useState } from "react";
import { useProgress } from "@/components/progress-provider";
import { useStudyCart } from "@/components/study-cart-provider";
import CourseOverview from "@/components/course-overview";
import { CourseSummary, ClassInfo } from "@/types/course";
import {
  FileText,
  FileIcon,
  FileSpreadsheet,
  Presentation,
  CheckCircle2,
  Circle,
  Layers,
  File,
  Plus,
  Check,

} from "lucide-react";

interface CourseContentProps {
  summary: CourseSummary;
  basePath: string;
  courseId: string;
}

function getFileIcon(filename: string) {
  const ext = filename.toLowerCase().split(".").pop();
  switch (ext) {
    case "pdf":
      return <FileText className="h-5 w-5 text-red-500" />;
    case "pptx":
    case "ppt":
      return <Presentation className="h-4 w-4 text-orange-500" />;
    case "xlsx":
    case "xls":
      return <FileSpreadsheet className="h-4 w-4 text-green-500" />;
    case "docx":
    case "doc":
      return <FileIcon className="h-4 w-4 text-blue-500" />;
    default:
      return <File className="h-4 w-4 text-slate-500" />;
  }
}

function isPDF(filename: string): boolean {
  return filename.toLowerCase().endsWith(".pdf");
}

function getPrimaryFilename(cls: any): string | null {
  if (cls.filename) return cls.filename;
  if (!cls.files || !Array.isArray(cls.files) || cls.files.length === 0) return null;

  // Prefer PDF if it exists in the files list
  const pdfFile = cls.files.find((f: any) => f.filename && isPDF(f.filename));
  if (pdfFile) return pdfFile.filename;

  // Fall back to the first available file
  return cls.files[0].filename || null;
}

export function CourseContent({ summary, basePath, courseId }: CourseContentProps) {
  const { toggleFileComplete, isFileComplete, toggleUnitComplete, getUnitProgress, getCourseProgress } = useProgress();
  const { addItem, removeItem, isInCart } = useStudyCart();
  const { progress } = useProgress();
  const fileRowRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const [openUnits, setOpenUnits] = useState<string[]>(["unit-1"]);

  // WebSocket sync and leaderboard is handled by `CourseOverview` component

  // Generate all file keys for progress tracking
  const allFileKeys: string[] = [];
  summary.units.forEach((unit) => {
    unit.classes.forEach((cls) => {
      const primaryFilename = getPrimaryFilename(cls);
      if (primaryFilename && cls.status === "success") {
        allFileKeys.push(`${unit.unit_number}-${cls.class_id}`);
      }
    });
  });

  const courseProgress = getCourseProgress(courseId, allFileKeys.length, allFileKeys);

  // On mount or when progress changes, scroll to last completed file and open its unit
  useEffect(() => {
    // find last completed key in traversal order
    let lastCompletedKey: string | null = null;
    summary.units.forEach((unit) => {
      unit.classes.forEach((cls) => {
        const primaryFilename = getPrimaryFilename(cls);
        const key = `${unit.unit_number}-${cls.class_id}`;
        if (primaryFilename && progress[courseId]?.[key]) {
          lastCompletedKey = key;
        }
      });
    });

    // If found, open the unit and scroll into view
    if (lastCompletedKey) {
      const [unitNumberStr] = (lastCompletedKey as string).split("-");
      const unitVal = `unit-${unitNumberStr}`;
      setOpenUnits((prev) => (prev.includes(unitVal) ? prev : [...prev, unitVal]));
      // small delay to ensure DOM nodes exist
      setTimeout(() => {
        const el = fileRowRefs.current[lastCompletedKey!];
        if (el && typeof el.scrollIntoView === "function") {
          el.scrollIntoView({ behavior: "smooth", block: "center" });
        }
      }, 150);
    }
  }, [progress, summary.units, courseId]);

  const handleAddToCart = (
    url: string,
    title: string,
    unitNumber: number,
    courseId?: string,
    fileKey?: string
  ) => {
    const id = url;
    if (isInCart(id)) {
      removeItem(id);
    } else {
      addItem({
        id,
        url,
        title,
        courseName: summary.course_name,
        unitNumber,
        courseId,
        fileKey,
      });
    }
  };

  return (
    <>
      <CourseOverview summary={summary} basePath={basePath} courseId={courseId} showLeaderboard={false} />

      {/* Quick Downloads removed per UI request */}

      {/* Units Accordion */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Layers className="h-5 w-5" />
            Course Units
          </CardTitle>
          <CardDescription>Browse all course materials by unit</CardDescription>
        </CardHeader>
        <CardContent>
          <Accordion type="multiple" value={openUnits} onValueChange={(v) => setOpenUnits(Array.isArray(v) ? v : [v])} className="w-full">
            {summary.units.map((unit) => {
              const unitFileKeys = unit.classes
                .filter((cls) => {
                  const primaryFilename = getPrimaryFilename(cls);
                  return primaryFilename && cls.status === "success";
                })
                .map((cls) => `${unit.unit_number}-${cls.class_id}`);
              const unitProgress = getUnitProgress(
                courseId,
                unit.unit_number,
                unitFileKeys.length,
                unitFileKeys
              );

              return (
                <AccordionItem key={unit.unit_number} value={`unit-${unit.unit_number}`}>
                  <AccordionTrigger className="hover:no-underline">
                    <div className="flex items-center justify-between w-full pr-4">
                      <div className="flex items-center gap-3">
                        <Badge variant="secondary">Unit {unit.unit_number}</Badge>
                        <span className="font-medium">
                          {unit.unit_name || `Unit ${unit.unit_number}`}
                        </span>
                        {unitProgress.percentage === 100 && (
                          <CheckCircle2 className="h-4 w-4 text-green-500" />
                        )}
                      </div>
                      <div className="flex items-center gap-3 text-sm text-slate-500">
                        <div className="hidden sm:flex items-center gap-2">
                          <Progress value={unitProgress.percentage} className="w-20 h-1.5" />
                          <span className="text-xs w-8">{unitProgress.percentage}%</span>
                        </div>
                        <span>{unit.total_files} files</span>
                        {unit.failed_files > 0 && (
                          <Badge variant="destructive" className="text-xs">
                            {unit.failed_files} failed
                          </Badge>
                        )}
                      </div>
                    </div>
                  </AccordionTrigger>
                  <AccordionContent>
                    {/* Unit-level toggle */}
                    <div className="flex items-center justify-between py-2 mb-2 border-b border-slate-100 dark:border-slate-800">
                      <div className="flex items-center gap-2">
                        <Button
                          variant={unitProgress.percentage === 100 ? "secondary" : "outline"}
                          size="sm"
                          className="gap-2"
                          onClick={(e) => {
                            e.stopPropagation();
                            const markComplete = unitProgress.percentage < 100;
                            toggleUnitComplete(courseId, unitFileKeys, markComplete);
                          }}
                        >
                          {unitProgress.percentage === 100 ? (
                            <>
                              <CheckCircle2 className="h-4 w-4 text-green-500" />
                              <span className="hidden sm:inline">Unit Complete</span>
                              <span className="sm:hidden">Done</span>
                            </>
                          ) : (
                            <>
                              <Circle className="h-4 w-4" />
                              <span className="hidden sm:inline">Mark Unit Complete</span>
                              <span className="sm:hidden">Mark</span>
                            </>
                          )}
                        </Button>
                      </div>
                      <div className="flex items-center gap-2">
                        {/* Add whole unit to study (merged PDF if available, otherwise enqueue files) */}
                        <Button
                          variant="outline"
                          size="sm"
                          className="gap-2"
                          onClick={(e) => {
                            e.stopPropagation();
                            // Always add individual slides/files from the unit (not the merged PDF)
                            unit.classes.forEach((cls) => {
                              const primaryFilename = getPrimaryFilename(cls);
                              if (primaryFilename && cls.status === "success") {
                                const filePath = `${basePath}/${unit.unit_directory}/${primaryFilename}`;
                                const fileKey = `${unit.unit_number}-${cls.class_id}`;
                                handleAddToCart(filePath, cls.class_name, unit.unit_number, courseId, fileKey);
                              }
                            });
                          }}
                        >
                          <FileText className="h-5 w-5" />
                          <span className="hidden sm:inline">Add Unit to Study</span>
                          <span className="sm:hidden">Add</span>
                        </Button>
                      </div>
                    </div>
                    <div className="space-y-2 pt-2">
                      {unit.classes.length > 0 ? (
                        unit.classes.map((file: ClassInfo, idx: number) => {
                          const fileKey = `${unit.unit_number}-${file.class_id}`;
                          const isComplete = isFileComplete(courseId, fileKey);
                          const primaryFilename = getPrimaryFilename(file);
                          const filePath = primaryFilename
                            ? `${basePath}/${unit.unit_directory}/${primaryFilename}`
                            : null;
                          const canPreview = primaryFilename && isPDF(primaryFilename);

                          return (
                            <div
                              ref={(el) => { fileRowRefs.current[fileKey] = el; }}
                              role="button"
                              tabIndex={0}
                              onKeyDown={(e) => {
                                if (e.key === "Enter" || e.key === " ") {
                                  e.preventDefault();
                                  if (canPreview && filePath) {
                                    handleAddToCart(filePath, file.class_name, unit.unit_number, courseId, fileKey);
                                  } else {
                                    toggleFileComplete(courseId, fileKey);
                                  }
                                }
                              }}
                              onClick={() => {
                                if (canPreview && filePath) {
                                  handleAddToCart(filePath, file.class_name, unit.unit_number, courseId, fileKey);
                                } else {
                                  toggleFileComplete(courseId, fileKey);
                                }
                              }}
                              key={idx}
                              className={`flex items-center justify-between p-3 rounded-lg transition-all duration-200 ${isComplete
                                  ? "bg-green-50 dark:bg-green-500/10 border border-green-200 dark:border-green-500/30"
                                  : "bg-slate-100/80 dark:bg-slate-800/40 hover:bg-slate-200/80 dark:hover:bg-slate-700/50 border border-transparent hover:border-slate-300 dark:hover:border-slate-600"
                                }`}
                            >
                              <div className="flex items-center gap-3 min-w-0">
                                {primaryFilename && file.status === "success" && (
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      toggleFileComplete(courseId, fileKey);
                                    }}
                                    className="flex-shrink-0"
                                  >
                                    {isComplete ? (
                                      <CheckCircle2 className="h-5 w-5 text-green-500" />
                                    ) : (
                                      <Circle className="h-5 w-5 text-slate-400 dark:text-slate-500 hover:text-slate-500 dark:hover:text-slate-400" />
                                    )}
                                  </button>
                                )}
                                {primaryFilename && getFileIcon(primaryFilename)}
                                <div className="min-w-0">
                                  <p
                                    className={`font-medium text-sm truncate ${isComplete ? "text-green-700 dark:text-green-400" : ""
                                      }`}
                                  >
                                    {primaryFilename || file.class_name}
                                  </p>
                                  <p className="text-xs text-slate-500">{file.class_name}</p>
                                </div>
                              </div>
                              {primaryFilename && file.status === "success" ? (
                                <div className="flex items-center gap-2">
                                  {canPreview && (() => {
                                    const inCart = isInCart(filePath!);
                                    return (
                                      <Button
                                        size="sm"
                                        variant={inCart ? "secondary" : "ghost"}
                                        className="gap-2"
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          handleAddToCart(
                                            filePath!,
                                            file.class_name,
                                            unit.unit_number,
                                            courseId,
                                            fileKey
                                          );
                                        }}
                                      >
                                        {inCart ? <Check className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
                                        <span className="hidden sm:inline">{inCart ? "Added" : "Study"}</span>
                                      </Button>
                                    );
                                  })()}

                                </div>
                              ) : (
                                <Badge variant="destructive">Failed</Badge>
                              )}
                            </div>
                          );
                        })
                      ) : (
                        <p className="text-sm text-slate-500 text-center py-4">
                          No files in this unit
                        </p>
                      )}
                    </div>
                  </AccordionContent>
                </AccordionItem>
              );
            })}
          </Accordion>
        </CardContent>
      </Card>
      {/* Render the live leaderboard after the units list */}
      <div className="mt-6">
        <CourseOverview summary={summary} basePath={basePath} courseId={courseId} showProgress={false} />
      </div>

    </>
  );
}
