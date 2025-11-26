export interface ClassInfo {
  class_number: number;
  class_id: string;
  class_name: string;
  filename: string | null;
  file_size: number | null;
  file_type: string | null;
  status: "success" | "failed";
}

export interface UnitInfo {
  unit_number: number;
  unit_id: string;
  unit_name: string;
  unit_directory: string;
  classes: ClassInfo[];
  total_files: number;
  failed_files: number;
  merged_pdf: string | null;
}

export interface CourseSummary {
  course_id: string;
  course_name: string;
  download_date: string;
  total_units: number;
  units: UnitInfo[];
  total_downloaded: number;
  total_failed: number;
  failure_log: string;
}
