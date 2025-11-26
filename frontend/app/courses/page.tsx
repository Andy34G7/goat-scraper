import { readdir, readFile } from "fs/promises";
import { join } from "path";
import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Header } from "@/components/header";
import { CourseSummary } from "@/types/course";
import { FolderOpen, CheckCircle2, XCircle, ArrowRight, ArrowLeft } from "lucide-react";

async function getAllCourses(): Promise<{ dir: string; summary: CourseSummary }[]> {
  const coursesPath = join(process.cwd(), "public", "courses");
  
  try {
    const entries = await readdir(coursesPath, { withFileTypes: true });
    const courseDirs = entries.filter((e) => e.isDirectory() && e.name.startsWith("course"));

    const courses = await Promise.all(
      courseDirs.map(async (dir) => {
        const dirPath = join(coursesPath, dir.name);
        const files = await readdir(dirPath);
        const summaryFile = files.find((f) => f.endsWith("_course_summary.json"));
        
        if (!summaryFile) return null;

        const summaryData = await readFile(join(dirPath, summaryFile), "utf-8");
        return { dir: dir.name, summary: JSON.parse(summaryData) as CourseSummary };
      })
    );

    return courses.filter((c): c is { dir: string; summary: CourseSummary } => c !== null);
  } catch {
    return [];
  }
}

function buildSearchItems(courses: { dir: string; summary: CourseSummary }[]) {
  const items: { type: "course" | "unit" | "file"; title: string; subtitle?: string; href: string; download?: boolean }[] = [];

  for (const { dir, summary } of courses) {
    items.push({
      type: "course",
      title: summary.course_name,
      subtitle: summary.course_id,
      href: `/course/${dir}`,
    });

    for (const unit of summary.units) {
      items.push({
        type: "unit",
        title: `Unit ${unit.unit_number}: ${unit.unit_name}`,
        subtitle: summary.course_name,
        href: `/course/${dir}#unit-${unit.unit_number}`,
      });

      for (const cls of unit.classes) {
        if (cls.filename && cls.status === "success") {
          items.push({
            type: "file",
            title: cls.class_name,
            subtitle: `Unit ${unit.unit_number}`,
            href: `/courses/${dir}/${unit.unit_directory}/${cls.filename}`,
            download: true,
          });
        }
      }
    }
  }

  return items;
}

export default async function CoursesPage() {
  const courses = await getAllCourses();
  const searchItems = buildSearchItems(courses);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50/50 to-indigo-50 dark:from-[#0f1219] dark:via-[#111827] dark:to-[#0f172a]">
      <Header searchItems={searchItems} />

      {/* Back Button */}
      <div className="container mx-auto px-6 pt-6">
        <Link href="/">
          <Button variant="ghost" size="sm" className="gap-2">
            <ArrowLeft className="h-4 w-4" />
            Back to Home
          </Button>
        </Link>
      </div>

      {/* Main Content */}
      <main className="container mx-auto px-6 py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-slate-900 dark:text-white mb-2">My Courses</h1>
          <p className="text-slate-600 dark:text-slate-400">
            {courses.length} course{courses.length !== 1 ? "s" : ""} available
          </p>
        </div>

        {courses.length === 0 ? (
          <Card className="text-center py-12">
            <CardContent>
              <FolderOpen className="h-16 w-16 mx-auto text-slate-300 dark:text-slate-600 mb-4" />
              <h3 className="text-xl font-semibold text-slate-700 dark:text-slate-300 mb-2">
                No Courses Found
              </h3>
              <p className="text-slate-500 dark:text-slate-400 mb-4">
                Run the scraper to download course materials first.
              </p>
              <code className="block bg-slate-100 dark:bg-slate-800/60 px-4 py-2 rounded-lg text-sm font-mono border border-slate-200 dark:border-slate-700">
                uv run main.py -c COURSE_CODE
              </code>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {courses.map(({ dir, summary }) => {
              const successRate = summary.total_downloaded > 0
                ? Math.round((summary.total_downloaded / (summary.total_downloaded + summary.total_failed)) * 100)
                : 0;

              return (
                <Link key={dir} href={`/course/${dir}`}>
                  <Card className="h-full hover:shadow-lg hover:border-indigo-300 dark:hover:border-indigo-500/50 transition-all cursor-pointer group">
                    <CardHeader>
                      <div className="flex items-start justify-between">
                        <Badge variant={successRate === 100 ? "default" : "secondary"} className="mb-2">
                          {summary.course_id}
                        </Badge>
                        <Badge variant={summary.total_failed > 0 ? "destructive" : "outline"}>
                          {successRate}%
                        </Badge>
                      </div>
                      <CardTitle className="text-lg group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition-colors">
                        {summary.course_name.split("-").pop()?.trim() || summary.course_name}
                      </CardTitle>
                      <CardDescription>
                        {summary.course_name.split("-")[0]?.trim()}
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="grid grid-cols-3 gap-4 text-center mb-4">
                        <div>
                          <p className="text-2xl font-bold text-slate-900 dark:text-white">
                            {summary.total_units}
                          </p>
                          <p className="text-xs text-slate-500">Units</p>
                        </div>
                        <div className="flex flex-col items-center">
                          <div className="flex items-center gap-1">
                            <CheckCircle2 className="h-4 w-4 text-green-500" />
                            <span className="text-lg font-semibold">{summary.total_downloaded}</span>
                          </div>
                          <p className="text-xs text-slate-500">Files</p>
                        </div>
                        <div className="flex flex-col items-center">
                          <div className="flex items-center gap-1">
                            <XCircle className="h-4 w-4 text-red-500" />
                            <span className="text-lg font-semibold">{summary.total_failed}</span>
                          </div>
                          <p className="text-xs text-slate-500">Failed</p>
                        </div>
                      </div>
                      
                      <div className="flex items-center justify-between text-sm text-slate-500">
                        <span>Downloaded {new Date(summary.download_date).toLocaleDateString()}</span>
                        <ArrowRight className="h-4 w-4 group-hover:translate-x-1 transition-transform" />
                      </div>
                    </CardContent>
                  </Card>
                </Link>
              );
            })}
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-200 dark:border-slate-700/60 bg-white/50 dark:bg-slate-900/50 backdrop-blur-sm mt-auto">
        <div className="container mx-auto px-6 py-8">
          <div className="flex flex-col md:flex-row justify-between items-center gap-4">
            <p className="text-sm text-slate-500 dark:text-slate-400">
              ❤️
            </p>
            <div className="flex gap-4 text-sm text-slate-500 dark:text-slate-400">
              <a href="https://github.com/polarhive/goat-scraper" target="_blank" rel="noopener" className="hover:text-indigo-600 dark:hover:text-indigo-400">
                GitHub
              </a>
              <span>•</span>
              <span>Press ⌘K to search</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
