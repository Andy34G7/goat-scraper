"use client";

import React from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { BookOpen, CheckCircle2, Layers } from "lucide-react";
import { useProgress } from "@/components/progress-provider";
import { useProgressSync } from "@/components/use-progress-sync";
import { Leaderboard } from "@/components/leaderboard";
import { CourseSummary } from "@/types/course";

function isPDF(filename: string): boolean {
  return filename.toLowerCase().endsWith(".pdf");
}

function getPrimaryFilename(cls: any): string | null {
  if (cls.filename) return cls.filename;
  if (!cls.files || !Array.isArray(cls.files) || cls.files.length === 0) return null;

  const pdfFile = cls.files.find((f: any) => f.filename && isPDF(f.filename));
  if (pdfFile) return pdfFile.filename;

  return cls.files[0].filename || null;
}

interface CourseOverviewProps {
  summary: CourseSummary;
  basePath: string;
  courseId: string;
  showProgress?: boolean;
  showLeaderboard?: boolean;
}
export default function CourseOverview({ summary, basePath, courseId, showProgress = true, showLeaderboard = true }: CourseOverviewProps) {
  const { getUnitProgress, getCourseProgress } = useProgress();
  const { leaderboard, username, isConnected, currentUserRank, updateUsername } = useProgressSync(courseId);
  const [currentUserId, setCurrentUserId] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (typeof window !== "undefined") {
      setCurrentUserId(localStorage.getItem("progress-user-id"));
    }
  }, []);

  // build file keys
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

  const progressSection = (
    <div className="w-full mb-4">
      <Card className="p-3">
        <CardHeader className="p-0 mb-2">
          <CardTitle className="text-md flex items-center gap-2">
            <BookOpen className="h-4 w-4" />
            Your Progress
          </CardTitle>
          <CardDescription className="text-sm text-slate-500">{courseProgress.completed} of {courseProgress.total} materials</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <div className="space-y-3">
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-600 dark:text-slate-400 text-sm">
                {courseProgress.completed} / {courseProgress.total}
              </span>
              <span className="font-semibold text-sm">
                {courseProgress.percentage}%
              </span>
            </div>
            <Progress value={courseProgress.percentage} className="h-2" />
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 pt-2">
              {summary.units.map((unit) => {
                const unitFileKeys = unit.classes
                  .filter((cls) => getPrimaryFilename(cls) && cls.status === "success")
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
                    className="p-2 rounded-md bg-slate-100/60 dark:bg-slate-800/30 border border-slate-200/30 dark:border-slate-700/30"
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <Badge variant="outline" className="text-[11px]">
                        Unit {unit.unit_number}
                      </Badge>
                      {unitProgress.percentage === 100 && (
                        <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
                      )}
                    </div>
                    <Progress value={unitProgress.percentage} className="h-1" />
                    <p className="text-[11px] text-slate-500 mt-1">
                      {unitProgress.completed}/{unitProgress.total}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );

  const leaderboardSection = (
    <div className="w-full mb-4">
      <div className="space-y-0">
        <Leaderboard
          entries={leaderboard}
          currentUserId={currentUserId}
          currentUserRank={currentUserRank}
          isConnected={isConnected}
          username={username}
          onUpdateUsername={updateUsername}
        />
      </div>
    </div>
  );

  if (showProgress && showLeaderboard) {
    return (
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6 items-start">
        <div className="lg:col-span-2">{progressSection}</div>
        <div className="lg:col-span-1">{leaderboardSection}</div>
      </div>
    );
  }

  if (showProgress && !showLeaderboard) {
    return <div className="mb-6">{progressSection}</div>;
  }

  if (!showProgress && showLeaderboard) {
    return <div className="mb-6">{leaderboardSection}</div>;
  }

  return null;
}
