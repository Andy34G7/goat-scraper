import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Header } from "@/components/header";
import { ThemeToggle } from "@/components/theme-toggle";
import { CourseSummary } from "@/types/course";
import { getAllCourses, getCoursesBaseURL } from "@/lib/courses-api";
import {
  ArrowRight,
  GraduationCap,
  Download,
  Zap,
  Shield,
  BookOpen,
  FileText,
  Layers,
  CheckCircle
} from "lucide-react";

function buildSearchItems(courses: { dir: string; summary: CourseSummary }[]) {
  const items: { type: "course" | "unit" | "file"; title: string; subtitle?: string; href: string; download?: boolean }[] = [];
  const baseURL = getCoursesBaseURL();

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
            href: `${baseURL}/${dir}/${unit.unit_directory}/${cls.filename}`,
            download: true,
          });
        }
      }
    }
  }

  return items;
}

export default async function HomePage() {
  const courses = await getAllCourses();
  const searchItems = buildSearchItems(courses);

  return (
    <div className="min-h-screen flex flex-col bg-gradient-to-br from-slate-50 via-blue-50/50 to-indigo-50 dark:from-[#0f1219] dark:via-[#111827] dark:to-[#0f172a]">
      <Header searchItems={searchItems} />

      {/* Hero Section */}
      <section className="relative overflow-hidden flex-1 flex items-center">
        <div className="absolute inset-0 bg-gradient-to-r from-indigo-500/10 via-purple-500/10 to-pink-500/10 dark:from-indigo-500/5 dark:via-purple-500/5 dark:to-pink-500/5" />

        {/* Decorative elements */}
        <div className="absolute top-20 right-20 w-72 h-72 bg-indigo-400/20 dark:bg-indigo-500/10 rounded-full blur-3xl" />
        <div className="absolute bottom-20 left-20 w-96 h-96 bg-purple-400/20 dark:bg-purple-500/10 rounded-full blur-3xl" />

        <div className="container mx-auto px-6 py-12 md:py-20 relative">
          <div className="max-w-3xl mx-auto text-center">
            <h1 className="text-4xl md:text-5xl lg:text-6xl font-extrabold text-slate-900 dark:text-white mb-4 leading-tight animate-in fade-in slide-in-from-bottom-4 duration-700 ease-out">
              Your Course Materials,
              <br />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 to-purple-600 dark:from-indigo-400 dark:to-purple-400">
                Organized
              </span>
            </h1>
            <p className="text-lg md:text-xl text-slate-600 dark:text-slate-400 mb-6 leading-relaxed max-w-2xl mx-auto animate-in fade-in slide-in-from-bottom-6 duration-700 delay-150 ease-out fill-mode-backwards">
              Access all your course materials in one place. Preview PDFs, track progress, and study smarter.
            </p>

            {/* CTA Button */}
            <div className="mb-8 animate-in fade-in slide-in-from-bottom-8 duration-700 delay-300 ease-out fill-mode-backwards">
              <Link href="/courses">
                <Button size="lg" className="px-6 py-3 rounded-full text-lg bg-indigo-600 hover:bg-indigo-700 text-white shadow-md shadow-indigo-500/20 transition-transform hover:-translate-y-0.5">
                  Browse Courses
                  <ArrowRight className="h-5 w-5 ml-3" />
                </Button>
              </Link>
            </div>

            {/* Feature Cards */}
            <div className="grid md:grid-cols-3 gap-6 max-w-4xl mx-auto animate-in fade-in slide-in-from-bottom-10 duration-700 delay-500 ease-out fill-mode-backwards">
              <div className="p-6 rounded-2xl bg-white/90 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700/60 backdrop-blur-sm hover:shadow-xl transition-all duration-300 hover:-translate-y-1 hover:border-indigo-500/30 dark:hover:border-indigo-400/30 group">
                <div className="w-12 h-12 rounded-xl bg-indigo-50 dark:bg-indigo-900/20 flex items-center justify-center mb-4 mx-auto ring-1 ring-indigo-100 dark:ring-indigo-800/30 group-hover:bg-indigo-100 dark:group-hover:bg-indigo-900/40 transition-colors">
                  <FileText className="h-6 w-6 text-indigo-600 dark:text-indigo-400 group-hover:scale-110 transition-transform" />
                </div>
                <h3 className="font-semibold text-slate-900 dark:text-white mb-2">PDF Preview</h3>
                <p className="text-sm text-slate-600 dark:text-slate-400">
                  View PDFs directly in your browser with a side panel viewer.
                </p>
              </div>
              <div className="p-6 rounded-2xl bg-white/90 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700/60 backdrop-blur-sm hover:shadow-xl transition-all duration-300 hover:-translate-y-1 hover:border-green-500/30 dark:hover:border-green-400/30 group">
                <div className="w-12 h-12 rounded-xl bg-green-50 dark:bg-green-900/20 flex items-center justify-center mb-4 mx-auto ring-1 ring-green-100 dark:ring-green-800/30 group-hover:bg-green-100 dark:group-hover:bg-green-900/40 transition-colors">
                  <CheckCircle className="h-6 w-6 text-green-600 dark:text-green-400 group-hover:scale-110 transition-transform" />
                </div>
                <h3 className="font-semibold text-slate-900 dark:text-white mb-2">Progress Tracking</h3>
                <p className="text-sm text-slate-600 dark:text-slate-400">
                  Mark materials as complete and track your learning progress.
                </p>
              </div>
              <div className="p-6 rounded-2xl bg-white/90 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700/60 backdrop-blur-sm hover:shadow-xl transition-all duration-300 hover:-translate-y-1 hover:border-purple-500/30 dark:hover:border-purple-400/30 group">
                <div className="w-12 h-12 rounded-xl bg-purple-50 dark:bg-purple-900/20 flex items-center justify-center mb-4 mx-auto ring-1 ring-purple-100 dark:ring-purple-800/30 group-hover:bg-purple-100 dark:group-hover:bg-purple-900/40 transition-colors">
                  <Layers className="h-6 w-6 text-purple-600 dark:text-purple-400 group-hover:scale-110 transition-transform" />
                </div>
                <h3 className="font-semibold text-slate-900 dark:text-white mb-2">Merged PDFs</h3>
                <p className="text-sm text-slate-600 dark:text-slate-400">
                  Download all unit materials as a single merged PDF.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Feature Pills */}
      <section className="border-t border-slate-200 dark:border-slate-700/60 bg-white/50 dark:bg-slate-900/50 backdrop-blur-sm">
        <div className="container mx-auto px-6 py-8">
          <div className="flex flex-wrap gap-3 justify-center">
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 text-sm shadow-sm">
              <Download className="h-4 w-4 text-indigo-500" />
              <span>Auto-merged PDFs</span>
            </div>
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 text-sm shadow-sm">
              <Zap className="h-4 w-4 text-yellow-500" />
              <span>Fast Search (⌘K)</span>
            </div>
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 text-sm shadow-sm">
              <Shield className="h-4 w-4 text-green-500" />
              <span>Offline Access</span>
            </div>
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 text-sm shadow-sm">
              <BookOpen className="h-4 w-4 text-purple-500" />
              <span>Progress Tracking</span>
            </div>
          </div>
        </div>
      </section>

    </div>
  );
}
