import { notFound } from "next/navigation";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Header } from "@/components/header";
import { CourseContent } from "@/components/course-content";
import { getCourseById, getCoursesBaseURL } from "@/lib/courses-api";
import {
  ArrowLeft,
  CheckCircle2,
  XCircle,
  Calendar,
  Layers,
} from "lucide-react";

interface Props {
  params: Promise<{ id: string }>;
}

export default async function CoursePage({ params }: Props) {
  const { id } = await params;
  const data = await getCourseById(id);

  if (!data) {
    notFound();
  }

  const { summary, dir } = data;
  const baseURL = getCoursesBaseURL();
  const basePath = `${baseURL}/${dir}`;
  const successRate =
    summary.total_downloaded > 0
      ? Math.round(
          (summary.total_downloaded / (summary.total_downloaded + summary.total_failed)) * 100
        )
      : 0;

  // Build search items for this course
  const searchItems: { type: "course" | "unit" | "file"; title: string; subtitle?: string; href: string; download?: boolean }[] = [
    {
      type: "course",
      title: summary.course_name,
      subtitle: summary.course_id,
      href: `/course/${dir}`,
    },
  ];

  for (const unit of summary.units) {
    searchItems.push({
      type: "unit",
      title: `Unit ${unit.unit_number}: ${unit.unit_name}`,
      subtitle: summary.course_name,
      href: `/course/${dir}#unit-${unit.unit_number}`,
    });

    for (const cls of unit.classes) {
      if (cls.filename && cls.status === "success") {
        searchItems.push({
          type: "file",
          title: cls.class_name,
          subtitle: `Unit ${unit.unit_number}`,
          href: `${baseURL}/${dir}/${unit.unit_directory}/${cls.filename}`,
          download: true,
        });
      }
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50/50 to-indigo-50 dark:from-[#0f1219] dark:via-[#111827] dark:to-[#0f172a]">
      <Header searchItems={searchItems} />

      {/* Back Button */}
      <div className="container mx-auto px-6 pt-6">
        <Link href="/">
          <Button variant="ghost" size="sm" className="gap-2">
            <ArrowLeft className="h-4 w-4" />
            Back to Courses
          </Button>
        </Link>
      </div>

      {/* Main Content */}
      <main className="container mx-auto px-6 py-6">
        {/* Course Header */}
        <div className="mb-8">
          <div className="flex flex-wrap items-center gap-2 mb-3">
            <Badge variant="default">{summary.course_id}</Badge>
            <Badge variant={summary.total_failed > 0 ? "destructive" : "outline"}>
              {successRate}% downloaded
            </Badge>
          </div>
          <h2 className="text-3xl font-bold text-slate-900 dark:text-white mb-2">
            {summary.course_name}
          </h2>
          <div className="flex flex-wrap gap-6 text-sm text-slate-600 dark:text-slate-400 mt-4">
            <div className="flex items-center gap-2">
              <Layers className="h-4 w-4" />
              <span>{summary.total_units} Units</span>
            </div>
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-green-500" />
              <span>{summary.total_downloaded} Files Downloaded</span>
            </div>
            <div className="flex items-center gap-2">
              <XCircle className="h-4 w-4 text-red-500" />
              <span>{summary.total_failed} Failed</span>
            </div>
            <div className="flex items-center gap-2">
              <Calendar className="h-4 w-4" />
              <span>{new Date(summary.download_date).toLocaleDateString()}</span>
            </div>
          </div>
        </div>

        {/* Course Content with PDF Preview and Progress Tracking */}
        <CourseContent summary={summary} basePath={basePath} courseId={dir} />
      </main>
    </div>
  );
}
