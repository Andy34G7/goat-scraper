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
import { useProgress } from "@/components/progress-provider";
import { useStudyCart } from "@/components/study-cart-provider";
import { CourseSummary, ClassInfo } from "@/types/course";
import {
  FileText,
  Download,
  FileIcon,
  FileSpreadsheet,
  Presentation,
  CheckCircle2,
  Circle,
  Layers,
  File,
  Plus,
  Check,
  BookOpen,
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
      return <FileText className="h-4 w-4 text-red-500" />;
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

export function CourseContent({ summary, basePath, courseId }: CourseContentProps) {
  const { toggleFileComplete, isFileComplete, toggleUnitComplete, getUnitProgress, getCourseProgress } = useProgress();
  const { addItem, removeItem, isInCart } = useStudyCart();

  // Generate all file keys for progress tracking
  const allFileKeys: string[] = [];
  summary.units.forEach((unit) => {
    unit.classes.forEach((cls) => {
      if (cls.filename && cls.status === "success") {
        allFileKeys.push(`${unit.unit_number}-${cls.class_id}`);
      }
    });
  });

  const courseProgress = getCourseProgress(courseId, allFileKeys.length, allFileKeys);

  const handleAddToCart = (url: string, title: string, unitNumber: number) => {
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
      });
    }
  };

  return (
    <>
      {/* Overall Progress Card */}
      <Card className="mb-8">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <BookOpen className="h-5 w-5" />
            Your Progress
          </CardTitle>
          <CardDescription>
            Track your learning progress through the course materials
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-600 dark:text-slate-400">
                {courseProgress.completed} of {courseProgress.total} materials completed
              </span>
              <span className="font-semibold">
                {courseProgress.percentage}%
              </span>
            </div>
            <Progress value={courseProgress.percentage} className="h-3" />
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-2">
              {summary.units.map((unit) => {
                const unitFileKeys = unit.classes
                  .filter((cls) => cls.filename && cls.status === "success")
                  .map((cls) => `${unit.unit_number}-${cls.class_id}`);
                const unitProgress = getUnitProgress(
                  courseId,
                  unit.unit_number,
                  unitFileKeys.length,
                  unitFileKeys
                );
                return (
                  <div
                    key={unit.unit_number}
                    className="p-3 rounded-lg bg-slate-100/80 dark:bg-slate-800/40 border border-slate-200/50 dark:border-slate-700/50"
                  >
                    <div className="flex items-center gap-2 mb-2">
                      <Badge variant="outline" className="text-xs">
                        Unit {unit.unit_number}
                      </Badge>
                      {unitProgress.percentage === 100 && (
                        <CheckCircle2 className="h-4 w-4 text-green-500" />
                      )}
                    </div>
                    <Progress value={unitProgress.percentage} className="h-1.5" />
                    <p className="text-xs text-slate-500 mt-1">
                      {unitProgress.completed}/{unitProgress.total}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Merged PDF Download */}
      <Card className="mb-8">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Download className="h-5 w-5" />
            Quick Downloads
          </CardTitle>
          <CardDescription>Download merged PDFs for each unit</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-3">
            {summary.units.map((unit) => {
              if (!unit.merged_pdf) return null;
              const mergedPdf = `${basePath}/${unit.unit_directory}/${unit.merged_pdf}`;
              const inCart = isInCart(mergedPdf);
              return (
                <div key={unit.unit_number} className="flex gap-1">
                  <Button
                    variant={inCart ? "default" : "outline"}
                    className={`gap-2 ${inCart ? "bg-indigo-600 hover:bg-indigo-700" : ""}`}
                    onClick={() =>
                      handleAddToCart(mergedPdf, `Unit ${unit.unit_number} Merged`, unit.unit_number)
                    }
                  >
                    {inCart ? <Check className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
                    {inCart ? "Added" : "Add to Study"}
                  </Button>
                  <a href={mergedPdf} download className="inline-flex">
                    <Button variant="outline" className="gap-2">
                      <FileText className="h-4 w-4 text-red-500" />
                      Unit {unit.unit_number} Merged PDF
                    </Button>
                  </a>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

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
          <Accordion type="multiple" defaultValue={["unit-1"]} className="w-full">
            {summary.units.map((unit) => {
              const unitFileKeys = unit.classes
                .filter((cls) => cls.filename && cls.status === "success")
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
                      <span className="text-sm text-slate-500">
                        {unitProgress.completed}/{unitProgress.total} completed
                      </span>
                      <Button
                        variant={unitProgress.percentage === 100 ? "secondary" : "outline"}
                        size="sm"
                        className="gap-2"
                        onClick={() => {
                          const markComplete = unitProgress.percentage < 100;
                          toggleUnitComplete(courseId, unitFileKeys, markComplete);
                        }}
                      >
                        {unitProgress.percentage === 100 ? (
                          <>
                            <CheckCircle2 className="h-4 w-4 text-green-500" />
                            Unit Complete
                          </>
                        ) : (
                          <>
                            <Circle className="h-4 w-4" />
                            Mark Unit Complete
                          </>
                        )}
                      </Button>
                    </div>
                    <div className="space-y-2 pt-2">
                      {unit.classes.length > 0 ? (
                        unit.classes.map((file: ClassInfo, idx: number) => {
                          const fileKey = `${unit.unit_number}-${file.class_id}`;
                          const isComplete = isFileComplete(courseId, fileKey);
                          const filePath = file.filename
                            ? `${basePath}/${unit.unit_directory}/${file.filename}`
                            : null;
                          const canPreview = file.filename && isPDF(file.filename);

                          return (
                            <div
                              key={idx}
                              className={`flex items-center justify-between p-3 rounded-lg transition-all duration-200 ${
                                isComplete
                                  ? "bg-green-50 dark:bg-green-500/10 border border-green-200 dark:border-green-500/30"
                                  : "bg-slate-100/80 dark:bg-slate-800/40 hover:bg-slate-200/80 dark:hover:bg-slate-700/50 border border-transparent hover:border-slate-300 dark:hover:border-slate-600"
                              }`}
                            >
                              <div className="flex items-center gap-3 min-w-0">
                                {file.filename && file.status === "success" && (
                                  <button
                                    onClick={() => toggleFileComplete(courseId, fileKey)}
                                    className="flex-shrink-0"
                                  >
                                    {isComplete ? (
                                      <CheckCircle2 className="h-5 w-5 text-green-500" />
                                    ) : (
                                      <Circle className="h-5 w-5 text-slate-400 dark:text-slate-500 hover:text-slate-500 dark:hover:text-slate-400" />
                                    )}
                                  </button>
                                )}
                                {file.filename && getFileIcon(file.filename)}
                                <div className="min-w-0">
                                  <p
                                    className={`font-medium text-sm truncate ${
                                      isComplete ? "text-green-700 dark:text-green-400" : ""
                                    }`}
                                  >
                                    {file.filename || file.class_name}
                                  </p>
                                  <p className="text-xs text-slate-500">{file.class_name}</p>
                                </div>
                              </div>
                              {file.filename && file.status === "success" ? (
                                <div className="flex items-center gap-2">
                                  {canPreview && (() => {
                                    const inCart = isInCart(filePath!);
                                    return (
                                      <Button
                                        size="sm"
                                        variant={inCart ? "secondary" : "ghost"}
                                        className="gap-2"
                                        onClick={() => handleAddToCart(filePath!, file.class_name, unit.unit_number)}
                                      >
                                        {inCart ? <Check className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
                                        {inCart ? "Added" : "Study"}
                                      </Button>
                                    );
                                  })()}
                                  <a href={filePath!} download>
                                    <Button size="sm" variant="ghost" className="gap-2">
                                      <Download className="h-4 w-4" />
                                      Download
                                    </Button>
                                  </a>
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

    </>
  );
}
