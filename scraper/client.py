#!/usr/bin/env python3
"""
PESU Academy PDF Fetcher

Interactive tool to fetch course PDFs from PESU Academy using the following workflow:
1. Get course codes from /Academy/a/g/getSubjectsCode
2. Get unit IDs for a course from /Academy/a/i/getCourse/[course_id]
3. Get classes for a unit from /Academy/a/i/getCourseClasses/[unit_id]
4. Download PDF from /Academy/s/studentProfilePESUAdmin
"""

from typing import Optional, Dict, List, Any
import re
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from .utils import logger, compute_file_sha256

class AuthenticationError(Exception):
    """Raised when authentication with PESU Academy fails."""

    pass
class PDFDownloadError(Exception):
    """Raised when PDF download encounters an error."""

    pass
class PESUPDFFetcher:
    BASE_URL = "https://www.pesuacademy.com/Academy"

    def __init__(self, username: str, password: str) -> None:
        self.session = requests.Session()
        self.username = username
        self.password = password
        # Track whether we have a valid authenticated session (cookie-based or validated)
        self._authenticated = False
        logger.debug(f"Initialized PDF fetcher for user: {username}")

    def _extract_csrf_token(self, html_content: str) -> str:
        """Extract CSRF token from HTML content using multiple heuristics:
        - hidden input named _csrf
        - meta tags like _csrf, csrf-token, csrf
        - inline JS assignment patterns
        - any UUID-like token as fallback
        Raises AuthenticationError if nothing found.
        """
        soup = BeautifulSoup(html_content, "html.parser")

        # 1) standard hidden input
        csrf_input = soup.find("input", {"name": "_csrf"})
        if csrf_input and csrf_input.get("value"):
            return csrf_input.get("value")  # type: ignore

        # 2) meta tags
        for meta_name in ("_csrf", "csrf-token", "csrf"):
            m = soup.find("meta", {"name": meta_name})
            if m and m.get("content"):
                return m.get("content")  # type: ignore

        # 3) JS inline assignment e.g. _csrf = 'uuid' or "_csrf":"uuid"
        m = re.search(
            r"_csrf['\"]?\s*[:=]\s*['\"]([0-9a-fA-F-]{8,})['\"]", html_content
        )
        if m:
            return m.group(1)

        # 4) fallback: any UUID in page
        m2 = re.search(
            r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
            html_content,
            re.I,
        )
        if m2:
            return m2.group(1)

        raise AuthenticationError("CSRF token not found in response")

    def login(self) -> None:
        """Authenticate with PESU Academy."""
        logger.debug("Starting authentication process...")

        try:
            # GET initial page (login landing)
            login_page_url = f"{self.BASE_URL}/"
            r0 = self.session.get(login_page_url, timeout=15)
            r0.raise_for_status()
            logger.debug(
                f"Login page GET status={getattr(r0, 'status_code', None)} url={getattr(r0, 'url', None)}"
            )
            logger.debug(
                f"Session cookies before login: {self.session.cookies.get_dict()}"
            )

            # Try multiple ways to obtain CSRF token (HTML > JS > cookie)
            try:
                csrf_token = self._extract_csrf_token(r0.text)
                csrf_source = "html"
            except AuthenticationError:
                csrf_token = self.session.cookies.get(
                    "XSRF-TOKEN"
                ) or self.session.cookies.get("CSRF-TOKEN")
                csrf_source = "cookie" if csrf_token else None

            if not csrf_token:
                raise AuthenticationError(
                    "Missing CSRF token (no HTML token or cookie)"
                )

            # Post login
            login_url = f"{self.BASE_URL}/j_spring_security_check"
            login_payload = {
                "j_username": self.username,
                "j_password": self.password,
                "_csrf": csrf_token,
            }

            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": r0.url,
                "Origin": "https://www.pesuacademy.com",
            }

            resp = self.session.post(
                login_url,
                data=login_payload,
                headers=headers,
                allow_redirects=True,
                timeout=15,
            )
            logger.debug(
                f"Login POST status={getattr(resp, 'status_code', None)} url={getattr(resp, 'url', None)}"
            )
            cookies = self.session.cookies.get_dict()
            logger.debug(f"Session cookies after login: {cookies}")

            # If server set a session cookie, accept it as authentication proof (minimize extra requests)
            if "JSESSIONID" in cookies or "SESSION" in cookies:
                self._authenticated = True
                logger.debug(
                    "✓ Authentication successful (session cookie present — skipping additional validation)"
                )
                return

            # Otherwise, inspect the POST response body for hints that we are logged in
            body = (resp.text or "").lower()
            if (
                "studentprofile" in body
                or "logout" in body
                or "/a/0" in getattr(resp, "url", "")
            ):
                self._authenticated = True
                logger.debug(
                    "✓ Authentication successful (detected profile content in POST response)"
                )
                return

            # Detect explicit failed login markers
            if (
                "j_username" in body
                or "j_spring_security_check" in body
                or ("invalid" in body and "login" in body)
            ):
                raise AuthenticationError(
                    "Authentication failed: login page or error detected after POST"
                )

            # Ambiguous case: try https alternative once (if redirect to http), and only then validate profile to confirm
            try:
                if getattr(resp, "url", "").startswith("http://"):
                    alt = "https://" + resp.url.split("://", 1)[1]
                    alt_resp = self.session.get(alt, allow_redirects=True, timeout=15)
                    alt_body = (alt_resp.text or "").lower()
                    if alt_resp.status_code < 400 and (
                        "studentprofile" in alt_body
                        or "logout" in alt_body
                        or "/a/0" in getattr(alt_resp, "url", "")
                    ):
                        self._authenticated = True
                        logger.debug(
                            "✓ Authentication successful (https fallback detected profile)"
                        )
                        return
            except Exception:
                pass

            # Last resort: perform a single profile validation request
            self._validate_authentication()
            self._authenticated = True
            logger.debug("✓ Authentication successful (validated via profile check)")

        except requests.RequestException as e:
            raise AuthenticationError(f"Network error during authentication: {e}")
        except Exception as e:
            raise AuthenticationError(f"Authentication failed: {e}")

    def _validate_authentication(self) -> None:
        """Validate that authentication was successful using heuristics on profile page."""
        profile_url = f"{self.BASE_URL}/s/studentProfilePESU"

        try:
            profile_response = self.session.get(
                profile_url, allow_redirects=True, timeout=15
            )
            logger.debug(
                f"Profile fetch status={getattr(profile_response, 'status_code', None)} url={getattr(profile_response, 'url', None)}"
            )
            app_body = (profile_response.text or "").lower()

            if profile_response.status_code == 200:
                # Heuristics for successful login
                if (
                    "studentprofile" in app_body
                    or "logout" in app_body
                    or "/a/0" in getattr(profile_response, "url", "")
                ):
                    self._authenticated = True
                    return

                # Detect login form indicating failed auth
                if re.search(r'name=["\']j_username["\']', app_body):
                    raise AuthenticationError(
                        "Authentication failed: login form detected after login"
                    )

                raise AuthenticationError(
                    "Authentication failed: unexpected profile response"
                )

            elif profile_response.status_code in (301, 302):
                raise AuthenticationError("Authentication failed: redirected to login")

            elif profile_response.status_code == 404:
                # Sometimes servers return 404 for certain internal endpoints even when a session exists.
                cookies = self.session.cookies.get_dict()
                logger.debug(f"Profile returned 404; cookies={cookies}")
                if "JSESSIONID" in cookies or "SESSION" in cookies:
                    logger.warning(
                        "Profile returned 404 but session cookie found; assuming authentication succeeded"
                    )
                    self._authenticated = True
                    return
                raise AuthenticationError("Authentication failed: profile returned 404")

            else:
                raise AuthenticationError(
                    f"Authentication failed: HTTP {profile_response.status_code}"
                )

        except requests.RequestException as e:
            raise AuthenticationError(f"Failed to validate authentication: {e}")

    def logout(self) -> None:
        """Logout from PESU Academy."""
        try:
            logout_url = f"{self.BASE_URL}/logout"
            self.session.get(logout_url)
            # Clear authenticated state
            self._authenticated = False
            logger.debug("✓ Session terminated")
        except requests.RequestException as e:
            logger.warning(f"Error during logout: {e}")

    def is_authenticated(self) -> bool:
        """Return whether this fetcher currently has a validated authenticated session."""
        return bool(self._authenticated)

    # ========================================================================
    # STEP 1: Get Subject Codes
    # ========================================================================

    def get_subjects_code(self) -> Optional[List[Dict[str, Any]]]:
        """
        Step 1: Get all available course codes.
        Endpoint: /Academy/a/g/getSubjectsCode
        Returns HTML <option> tags that need to be parsed.
        """
        logger.debug("\n=== STEP 1: Fetching Subject Codes ===")

        try:
            url = f"{self.BASE_URL}/a/g/getSubjectsCode"
            response = self.session.get(url)
            response.raise_for_status()

            # Parse HTML options
            soup = BeautifulSoup(response.text, "html.parser")
            options = soup.find_all("option")

            courses = []
            for option in options:
                course_id = option.get("value")
                course_name = option.text.strip()

                if course_id and course_name:
                    # Clean the course ID - remove any quotes, escape characters, and backslashes
                    course_id = str(course_id).strip()
                    # Remove escaped quotes
                    course_id = course_id.replace('\\"', "").replace("\\'", "")
                    # Remove regular quotes
                    course_id = course_id.strip('"').strip("'")
                    # Remove any remaining backslashes
                    course_id = course_id.replace("\\", "")

                    # Extract subject code (before the dash if present)
                    subject_code = (
                        course_name.split("-")[0] if "-" in course_name else course_name
                    )

                    courses.append(
                        {
                            "id": course_id,
                            "subjectCode": subject_code,
                            "subjectName": course_name,
                        }
                    )

            if courses:
                logger.debug(f"✓ Found {len(courses)} courses")
                return courses
            else:
                logger.warning("No courses found in response")
                return None

        except requests.RequestException as e:
            logger.error(
                f"FAILURE [get_subjects_code]: Network error fetching subjects - {e}"
            )
            logger.error(f"URL: {url}")
            return None
        except Exception as e:
            logger.error(f"FAILURE [get_subjects_code]: Error parsing subjects - {e}")
            logger.error(f"URL: {url}")
            return None

    # ========================================================================
    # STEP 2: Get Course Units
    # ========================================================================

    def get_course_units(self, course_id: str) -> Optional[List[Dict[str, Any]]]:
        """
        Step 2: Get units for a specific course.
        Endpoint: /Academy/a/i/getCourse/[course_id]
        Returns HTML <option> tags that need to be parsed.
        """
        logger.debug(f"\n=== STEP 2: Fetching Units for Course {course_id} ===")

        try:
            url = f"{self.BASE_URL}/a/i/getCourse/{course_id}"
            response = self.session.get(url)
            response.raise_for_status()

            # The response is JSON-encoded HTML string
            html_content = (
                response.json()
                if response.headers.get("Content-Type", "").startswith(
                    "application/json"
                )
                else response.text
            )

            # Parse HTML options
            soup = BeautifulSoup(html_content, "html.parser")
            options = soup.find_all("option")

            units = []
            for option in options:
                unit_id = option.get("value")
                unit_name = option.text.strip()

                if unit_id and unit_name:
                    # Clean the unit ID
                    unit_id = (
                        str(unit_id).strip().replace("\\", "").strip('"').strip("'")
                    )

                    # Extract unit number if present
                    unit_number = (
                        unit_name.split(":")[0].strip()
                        if ":" in unit_name
                        else unit_name
                    )

                    units.append(
                        {"id": unit_id, "unit": unit_name, "unitNumber": unit_number}
                    )

            if units:
                logger.debug(f"✓ Found {len(units)} units")
                return units
            else:
                logger.warning("No units found in response")
                return None

        except requests.RequestException as e:
            logger.error(
                f"FAILURE [get_course_units]: Network error fetching course units - {e}"
            )
            logger.error(f"Course ID: {course_id}")
            logger.error(f"URL: {url}")
            return None
        except Exception as e:
            logger.error(f"FAILURE [get_course_units]: Error parsing units - {e}")
            logger.error(f"Course ID: {course_id}")
            logger.error(f"URL: {url}")
            return None

    # ========================================================================
    # STEP 3: Get Unit Classes
    # ========================================================================

    def get_unit_classes(self, unit_id: str) -> Optional[List[Dict[str, Any]]]:
        """
        Step 3: Get classes for a specific unit.
        Endpoint: /Academy/a/i/getCourseClasses/[unit_id]
        Returns HTML <option> tags that need to be parsed.
        """
        logger.debug(f"\n=== STEP 3: Fetching Classes for Unit {unit_id} ===")

        try:
            url = f"{self.BASE_URL}/a/i/getCourseClasses/{unit_id}"
            response = self.session.get(url)
            response.raise_for_status()

            # The response is JSON-encoded HTML string
            html_content = (
                response.json()
                if response.headers.get("Content-Type", "").startswith(
                    "application/json"
                )
                else response.text
            )

            # Parse HTML options
            soup = BeautifulSoup(html_content, "html.parser")
            options = soup.find_all("option")

            classes = []
            for option in options:
                class_id = option.get("value")
                class_name = option.text.strip()

                if class_id and class_name:
                    # Clean the class ID
                    class_id = (
                        str(class_id).strip().replace("\\", "").strip('"').strip("'")
                    )

                    classes.append(
                        {
                            "id": class_id,
                            "className": class_name,
                            "classType": "Lecture",  # Default since not provided
                        }
                    )

            if classes:
                logger.debug(f"✓ Found {len(classes)} classes")
                return classes
            else:
                logger.warning("No classes found in response")
                return None

        except requests.RequestException as e:
            logger.error(
                f"FAILURE [get_unit_classes]: Network error fetching unit classes - {e}"
            )
            logger.error(f"Unit ID: {unit_id}")
            logger.error(f"URL: {url}")
            return None
        except Exception as e:
            logger.error(f"FAILURE [get_unit_classes]: Error parsing classes - {e}")
            logger.error(f"Unit ID: {unit_id}")
            logger.error(f"URL: {url}")
            return None

    # ========================================================================
    # STEP 4: Download File (PDF, PPTX, DOCX, etc.)
    # ========================================================================

    def download_pdf(
        self,
        course_id: str,
        class_id: str,
        output_path: Optional[Path] = None,
        class_name: Optional[str] = None,
        existing_summary: Optional[Dict] = None,
    ) -> List[Dict]:
        """
        Step 4: Download file(s) for a specific class (PDF, PPTX, DOCX, etc.).
        Returns a list of successfully downloaded file paths.
        If multiple files are found, all are downloaded with meaningful names based on link text.
        Endpoint: /Academy/s/studentProfilePESUAdmin with specific parameters
        """
        logger.debug("\n=== STEP 4: Downloading File ===")
        logger.debug(f"Course ID: {course_id}, Class ID: {class_id}")

        try:
            url = f"{self.BASE_URL}/s/studentProfilePESUAdmin"
            params = {
                "url": "studentProfilePESUAdmin",
                "controllerMode": "6403",
                "actionType": "60",
                "selectedData": course_id,
                "id": "2",
                "unitid": class_id,
            }

            response = self.session.get(url, params=params)
            response.raise_for_status()

            # Check if response is actually a PDF or HTML
            content_type = response.headers.get("Content-Type", "")

            if "application/pdf" in content_type:
                # Direct PDF download
                if output_path is None:
                    output_path = Path(f"course_{course_id}_class_{class_id}.pdf")

                with open(output_path, "wb") as f:
                    f.write(response.content)

                file_size = output_path.stat().st_size

                # Check if file is empty (0 bytes) and skip it
                if file_size == 0:
                    logger.warning("⚠ Downloaded PDF is empty (0 bytes), skipping")
                    output_path.unlink()  # Delete the 0-byte file
                    return []

                logger.debug(
                    f"✓ PDF downloaded successfully: {output_path} ({file_size:,} bytes)"
                )
                return [output_path]

            elif "text/html" in content_type:
                # Parse HTML to find download links (PDF, PPTX, DOCX, etc.)
                logger.debug("Response is HTML, parsing for download links...")
                soup = BeautifulSoup(response.text, "html.parser")

                # Look for links with onclick that call loadIframe, downloadslidecoursedoc, or downloadcoursedoc
                download_links = []
                import re

                # Search ALL elements with onclick attribute (not just <a> tags)
                for element in soup.find_all(onclick=True):
                    onclick = element.get("onclick", "")
                    text = element.text.strip()

                    # Check for downloadcoursedoc pattern (e.g., onclick="downloadcoursedoc('ID')")
                    if "downloadcoursedoc" in onclick:
                        # Extract ID from downloadcoursedoc('ID') pattern
                        match = re.search(r"downloadcoursedoc\('([^']+)'", onclick)
                        if match:
                            doc_id = match.group(1)
                            download_url = f"/Academy/s/referenceMeterials/downloadcoursedoc/{doc_id}"
                            full_url = f"https://www.pesuacademy.com{download_url}"

                            download_links.append(
                                {
                                    "text": text or "Course Document",
                                    "href": download_url,
                                    "full_url": full_url,
                                }
                            )
                            continue

                    # Check onclick for downloadslidecoursedoc pattern
                    if "downloadslidecoursedoc" in onclick:
                        # Extract the URL from onclick="loadIframe('/Academy/a/referenceMeterials/downloadslidecoursedoc/ID')"
                        match = re.search(r"loadIframe\('([^']+)'", onclick)
                        if match:
                            download_url = match.group(1)
                            # Remove the #view parameters
                            download_url = download_url.split("#")[0]

                            # Build full URL - if it starts with /Academy, use base domain only
                            if download_url.startswith("/Academy"):
                                full_url = f"https://www.pesuacademy.com{download_url}"
                            elif download_url.startswith("http"):
                                full_url = download_url
                            else:
                                full_url = f"{self.BASE_URL}/{download_url.lstrip('/')}"

                            download_links.append(
                                {
                                    "text": text or "Course Document",
                                    "href": download_url,
                                    "full_url": full_url,
                                }
                            )

                # Also check <a> tags for href-based download links
                for link in soup.find_all("a"):
                    href = link.get("href", "")
                    text = link.text.strip()

                    # Check for direct href links to downloadslidecoursedoc
                    if "downloadslidecoursedoc" in href:
                        download_url = href
                        download_url = download_url.split("#")[0]

                        if download_url.startswith("/Academy"):
                            full_url = f"https://www.pesuacademy.com{download_url}"
                        elif download_url.startswith("http"):
                            full_url = download_url
                        else:
                            full_url = f"{self.BASE_URL}/{download_url.lstrip('/')}"

                        download_links.append(
                            {
                                "text": text or "Course Document",
                                "href": download_url,
                                "full_url": full_url,
                            }
                        )

                    # Also check for any links with referenceMeterials or downloads
                    elif "referenceMeterials" in href or "download" in href.lower():
                        download_url = href
                        download_url = download_url.split("#")[0]

                        if download_url.startswith("/Academy"):
                            full_url = f"https://www.pesuacademy.com{download_url}"
                        elif download_url.startswith("http"):
                            full_url = download_url
                        else:
                            full_url = f"{self.BASE_URL}/{download_url.lstrip('/')}"

                        download_links.append(
                            {
                                "text": text or "Course Document",
                                "href": download_url,
                                "full_url": full_url,
                            }
                        )

                if not download_links:
                    logger.debug("No download links found in the response")
                    return []

                # Remove duplicates by URL while preserving order
                seen_urls = set()
                unique_links = []
                for link in download_links:
                    if link["full_url"] not in seen_urls:
                        seen_urls.add(link["full_url"])
                        unique_links.append(link)
                download_links = unique_links

                # Download ALL links (not just the first one)
                if len(download_links) > 1:
                    logger.debug(
                        f"Found {len(download_links)} download options, downloading all"
                    )
                    # Log each link for debugging
                    for idx, link in enumerate(download_links):
                        logger.debug(
                            f"  [{idx + 1}] {link['text'][:50]} -> {link['full_url']}"
                        )
                else:
                    logger.debug(
                        f"Found 1 download option: {download_links[0]['text']}"
                    )

                downloaded_files = []

                # Download each file
                for link_idx, selected_link in enumerate(download_links):
                    logger.debug(
                        f"Downloading [{link_idx + 1}/{len(download_links)}]: {selected_link['text']}"
                    )

                    # Download the selected file with proper headers (especially Referer)
                    logger.debug(f"Downloading from: {selected_link['full_url']}")
                    try:
                        # Add Referer header - required for downloadslidecoursedoc URLs
                        headers = {
                            "Referer": "https://www.pesuacademy.com/Academy/s/studentProfilePESU",
                            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        }
                        file_response = self.session.get(
                            selected_link["full_url"], stream=True, headers=headers
                        )
                        file_response.raise_for_status()
                    except requests.RequestException as e:
                        logger.error(f"Failed to download link {link_idx + 1}: {e}")
                        continue

                    # Try to get filename from Content-Disposition header first
                    content_disposition = file_response.headers.get(
                        "Content-Disposition", ""
                    )
                    original_filename = None
                    if "filename=" in content_disposition:
                        import re

                        # Try to extract filename from Content-Disposition
                        match = re.search(
                            r'filename[*]?=["\']?(?:UTF-8\'\')?([^"\';\n]+)',
                            content_disposition,
                        )
                        if match:
                            original_filename = match.group(1).strip()
                            logger.debug(
                                f"Original filename from server: {original_filename}"
                            )

                    # Determine file extension from content-type or original filename
                    file_content_type = file_response.headers.get("Content-Type", "")
                    extension = ".pdf"  # Default

                    # First try to get extension from original filename
                    if original_filename and "." in original_filename:
                        extension = "." + original_filename.rsplit(".", 1)[-1].lower()
                    # Otherwise use content-type
                    elif "application/pdf" in file_content_type:
                        extension = ".pdf"
                    elif (
                        "application/vnd.openxmlformats-officedocument.presentationml.presentation"
                        in file_content_type
                    ):
                        extension = ".pptx"
                    elif "application/vnd.ms-powerpoint" in file_content_type:
                        extension = ".ppt"
                    elif (
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                        in file_content_type
                    ):
                        extension = ".docx"
                    elif "application/msword" in file_content_type:
                        extension = ".doc"
                    elif (
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        in file_content_type
                    ):
                        extension = ".xlsx"
                    elif "application/vnd.ms-excel" in file_content_type:
                        extension = ".xls"
                    elif "application/octet-stream" in file_content_type:
                        # Generic binary - try to detect from magic bytes
                        # Read first few bytes to detect file type
                        first_chunk = next(
                            file_response.iter_content(chunk_size=8), b""
                        )
                        if first_chunk.startswith(b"PK"):
                            # ZIP-based format (pptx, docx, xlsx)
                            # Need more context, default to pptx for presentations
                            extension = ".pptx"
                            logger.debug(
                                "Detected ZIP-based format (likely Office document)"
                            )
                        elif first_chunk.startswith(b"%PDF"):
                            extension = ".pdf"

                        # Put the chunk back by creating a new iterator
                        def iter_with_first_chunk():
                            yield first_chunk
                            yield from file_response.iter_content(chunk_size=8192)

                        content_iterator = iter_with_first_chunk()
                    else:
                        content_iterator = None

                    if "content_iterator" not in locals() or content_iterator is None:
                        content_iterator = file_response.iter_content(chunk_size=8192)

                    logger.debug(f"Detected file type: {extension}")

                    # Determine output path with meaningful names for multiple files
                    if output_path is None:
                        # Try to get filename from URL or use default
                        filename = selected_link["href"].split("/")[-1]
                        if "." not in filename:
                            filename = f"class_{class_id}{extension}"
                        current_output_path = Path(filename)
                    else:
                        current_output_path = output_path
                        # If output path was provided but has wrong extension, update it
                        if current_output_path.suffix == ".pdf" and extension != ".pdf":
                            current_output_path = current_output_path.with_suffix(
                                extension
                            )

                    # For multiple files, use class_name + link_text for meaningful names
                    if len(download_links) > 1:
                        # Get the base prefix from output path (e.g., "05_" from "05_Kafka.pdf")
                        prefix = ""
                        if output_path:
                            # Extract numeric prefix like "05_"
                            stem = current_output_path.stem
                            import re

                            match = re.match(r"^(\d+)_", stem)
                            if match:
                                prefix = match.group(1) + "_"

                        # Use link text for the name, cleaning it up
                        link_text = selected_link["text"]
                        # Clean the link text: remove special chars, limit length
                        safe_link_text = "".join(
                            c if c.isalnum() or c in (" ", "-", "_") else "_"
                            for c in link_text
                        ).strip()
                        safe_link_text = "_".join(safe_link_text.split())[
                            :80
                        ]  # Join spaces with underscore, limit length

                        # Combine: prefix + class_name (if available) + link_text
                        if class_name:
                            # Extract class name without prefix
                            class_base = (
                                class_name.split(".", 1)[-1]
                                if "." in class_name
                                else class_name
                            )
                            class_base = "".join(
                                c if c.isalnum() or c in (" ", "-", "_") else "_"
                                for c in class_base
                            ).strip()
                            class_base = "_".join(class_base.split())[:50]
                            filename = (
                                f"{prefix}{class_base}_{safe_link_text}{extension}"
                            )
                        else:
                            filename = f"{prefix}{safe_link_text}{extension}"

                        current_output_path = current_output_path.parent / filename

                    # Save file (skip download if already present with checksum)
                    try:
                        # If file already exists on disk, try to skip re-downloading. Prefer verifying against
                        # the existing course summary JSON (if supplied) by comparing SHA; otherwise skip by existence.
                        if current_output_path.exists():
                            try:
                                existing_sha = compute_file_sha256(current_output_path)
                            except Exception:
                                existing_sha = None

                            skipped = False
                            if existing_summary is not None:
                                # Look up filename+sha in existing summary
                                def _match_in_summary(summary, filename, sha):
                                    if not summary:
                                        return False
                                    for u in summary.get("units", []):
                                        for c in u.get("classes", []):
                                            for f in c.get("files", []):
                                                if (
                                                    f.get("filename") == filename
                                                    and f.get("sha256") == sha
                                                ):
                                                    return True
                                    return False

                                if existing_sha and _match_in_summary(
                                    existing_summary,
                                    current_output_path.name,
                                    existing_sha,
                                ):
                                    logger.debug(
                                        f"Skipping download, file exists and checksum matches summary: {current_output_path.name}"
                                    )
                                    downloaded_files.append(
                                        {
                                            "path": current_output_path,
                                            "original_sha": None,
                                            "extension": current_output_path.suffix.lstrip(
                                                "."
                                            ),
                                        }
                                    )
                                    skipped = True

                            if not skipped:
                                # No existing summary match; skip re-download only if file is present and non-empty
                                if current_output_path.stat().st_size > 0:
                                    logger.debug(
                                        f"Skipping download, file already exists: {current_output_path.name}"
                                    )
                                    downloaded_files.append(
                                        {
                                            "path": current_output_path,
                                            "original_sha": None,
                                            "extension": current_output_path.suffix.lstrip(
                                                "."
                                            ),
                                        }
                                    )
                                    continue

                        with open(current_output_path, "wb") as f:
                            for chunk in content_iterator:
                                f.write(chunk)

                        file_size = current_output_path.stat().st_size

                        # Check if file is empty (0 bytes) and skip it
                        if file_size == 0:
                            logger.warning(
                                f"⚠ Skipping empty file (0 bytes): {current_output_path.name}"
                            )
                            logger.warning(f"Link text: {selected_link['text']}")
                            logger.warning(f"URL: {selected_link['full_url']}")
                            current_output_path.unlink()  # Delete the 0-byte file
                            continue

                        # Compute checksum of the original downloaded file (before conversion)
                        original_sha = None
                        try:
                            original_sha = compute_file_sha256(current_output_path)
                        except Exception as e:
                            logger.warning(
                                f"Failed to compute checksum for {current_output_path.name}: {e}"
                            )

                        logger.debug(
                            f"✓ File downloaded successfully: {current_output_path.name} ({file_size:,} bytes)"
                        )

                        # Defer conversions until after all downloads finish for the unit (helps with stability and concurrency)
                        if extension != ".pdf":
                            # We recorded original file and its checksum (above). Conversion will run in a separate pass after all downloads.
                            logger.debug(
                                f"Deferred conversion for {current_output_path.name} to post-download phase"
                            )
                        else:
                            # For direct PDFs, compute PDF checksum (we won't write sidecars)
                            try:
                                pdf_sha = compute_file_sha256(current_output_path)
                                # pdf_sha will be stored in JSON later
                            except Exception as e:
                                logger.warning(
                                    f"Failed to compute checksum for PDF {current_output_path.name}: {e}"
                                )

                        # Append structured file info (path + original sha) so callers can persist checksums into JSON later
                        downloaded_files.append(
                            {
                                "path": current_output_path,
                                "original_sha": original_sha,
                                "extension": extension.lstrip("."),
                            }
                        )

                    except IOError as e:
                        logger.error(f"Failed to save file {link_idx + 1}: {e}")
                        continue

                return downloaded_files

            else:
                logger.error(f"Unexpected content type: {content_type}")
                return []

        except requests.RequestException as e:
            logger.error(
                f"FAILURE [download_pdf]: Network error downloading file - {e}"
            )
            logger.error(f"Course ID: {course_id}")
            logger.error(f"Class ID: {class_id}")
            logger.error(f"Output Path: {output_path}")
            return []
        except IOError as e:
            logger.error(f"FAILURE [download_pdf]: File I/O error - {e}")
            logger.error(f"Course ID: {course_id}")
            logger.error(f"Class ID: {class_id}")
            logger.error(f"Output Path: {output_path}")
            return []
        except Exception as e:
            logger.error(f"FAILURE [download_pdf]: Unexpected error - {e}")
            logger.error(f"Course ID: {course_id}")
            logger.error(f"Class ID: {class_id}")
            logger.error(f"Output Path: {output_path}")
            return []
