import { readdir, readFile } from "fs/promises";
import { join } from "path";
import { CourseSummary } from "@/types/course";

// Backend URL for courses - if set, fetch from remote server
// Example: https://xyz.com/x/courses
const COURSES_API_URL = process.env.NEXT_PUBLIC_COURSES_API_URL;

// Check if we should use remote API
const useRemoteAPI = !!COURSES_API_URL;

/**
 * Get the base URL for course assets (PDFs, files, etc.)
 * Used in client components and for download links
 */
export function getCoursesBaseURL(): string {
  return COURSES_API_URL || "/courses";
}

/**
 * Fetch the list of course directories from the backend
 */
async function fetchCourseDirectories(): Promise<string[]> {
  if (!COURSES_API_URL) {
    throw new Error("COURSES_API_URL not configured");
  }

  // Expect a JSON file listing all course directories
  const response = await fetch(`${COURSES_API_URL}/index.json`, {
    next: { revalidate: 3600 }, // Cache for 1 hour
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch course index: ${response.status}`);
  }

  const data = await response.json();
  return data.courses || [];
}

/**
 * Fetch a course summary from the backend
 */
async function fetchCourseSummary(courseDir: string): Promise<CourseSummary | null> {
  if (!COURSES_API_URL) {
    throw new Error("COURSES_API_URL not configured");
  }

  try {
    // First, try to get the index of files in the course directory
    const indexResponse = await fetch(`${COURSES_API_URL}/${courseDir}/index.json`, {
      next: { revalidate: 3600 },
    });

    if (!indexResponse.ok) {
      // Fallback: try common summary file naming pattern
      const summaryResponse = await fetch(
        `${COURSES_API_URL}/${courseDir}/${courseDir.replace(/^course\d+_/, "")}_course_summary.json`,
        { next: { revalidate: 3600 } }
      );

      if (!summaryResponse.ok) {
        return null;
      }

      return await summaryResponse.json();
    }

    const indexData = await indexResponse.json();
    const summaryFile = indexData.summary_file;

    if (!summaryFile) {
      return null;
    }

    const summaryResponse = await fetch(`${COURSES_API_URL}/${courseDir}/${summaryFile}`, {
      next: { revalidate: 3600 },
    });

    if (!summaryResponse.ok) {
      return null;
    }

    return await summaryResponse.json();
  } catch {
    return null;
  }
}

/**
 * Get all courses - works both with local filesystem and remote API
 */
export async function getAllCourses(): Promise<{ dir: string; summary: CourseSummary }[]> {
  if (useRemoteAPI) {
    try {
      const courseDirs = await fetchCourseDirectories();

      const courses = await Promise.all(
        courseDirs.map(async (dir) => {
          const summary = await fetchCourseSummary(dir);
          if (!summary) return null;
          return { dir, summary };
        })
      );

      return courses.filter((c): c is { dir: string; summary: CourseSummary } => c !== null);
    } catch (error) {
      console.error("Failed to fetch courses from remote:", error);
      return [];
    }
  }

  // Local filesystem fallback
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

/**
 * Get a single course by ID - works both with local filesystem and remote API
 */
export async function getCourseById(id: string): Promise<{ summary: CourseSummary; dir: string } | null> {
  if (useRemoteAPI) {
    try {
      const summary = await fetchCourseSummary(id);
      if (!summary) return null;
      return { summary, dir: id };
    } catch {
      return null;
    }
  }

  // Local filesystem fallback
  const coursePath = join(process.cwd(), "public", "courses", id);

  try {
    const files = await readdir(coursePath);
    const summaryFile = files.find((f) => f.endsWith("_course_summary.json"));

    if (!summaryFile) return null;

    const summaryData = await readFile(join(coursePath, summaryFile), "utf-8");
    return { summary: JSON.parse(summaryData) as CourseSummary, dir: id };
  } catch {
    return null;
  }
}
