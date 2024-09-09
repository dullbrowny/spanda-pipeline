import requests
from docx import Document
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io
import re
import csv
from PyPDF2 import PdfFileReader

MOODLE_URL = 'https://taxila-spanda.wilp-connect.net/'
TOKEN = '738cbb551a279f2cd2799562ea2cbddf'
# MOODLE_URL = 'http://localhost/moodle/moodle-4.2.1'
# TOKEN = '80a42dd70578d1274a40e6994eafbb63'

# Function to make a Moodle API call
# Function to make a Moodle API call with detailed logging
def moodle_api_call(params, extra_params=None):
    if extra_params:
        params.update(extra_params)
    endpoint = f'{MOODLE_URL}/webservice/rest/server.php'
    response = requests.get(endpoint, params=params)
    print(f"API Call to {params['wsfunction']} - Status Code: {response.status_code}")
    print(f"API Request URL: {response.url}")  # Log the full URL for debugging

    try:
        result = response.json()
    except ValueError as e:
        raise ValueError(f"Error parsing JSON response: {response.text}") from e

    if 'exception' in result:
        raise Exception(f"Error: {result['exception']['message']}")

    return result

# Function to get enrolled users in a specific course
def get_enrolled_users(course_id):
    params = {
        'wstoken': TOKEN,
        'wsfunction': 'core_enrol_get_enrolled_users',
        'moodlewsrestformat': 'json',
        'courseid': course_id
    }
    return moodle_api_call(params)

# Function to check admin capabilities
def check_admin_capabilities():
    params = {
        'wstoken': TOKEN,
        'wsfunction': 'core_webservice_get_site_info',
        'moodlewsrestformat': 'json',
    }
    site_info = moodle_api_call(params)
    print("Site Info:", site_info)

# Function to get assignments for a specific course
def get_assignments(course_id):
    params = {
        'wstoken': TOKEN,
        'wsfunction': 'mod_assign_get_assignments',
        'moodlewsrestformat': 'json',
        'courseids[0]': course_id
    }
    
    extra_params = {'includenotenrolledcourses': 1}
    assignments = moodle_api_call(params, extra_params)
    
    if not assignments.get('courses'):
        print("No courses found.")
        return []

    courses = assignments['courses']
    if not courses:
        print("No courses returned from API.")
        return []

    course_data = courses[0]

    if 'assignments' not in course_data:
        print(f"No assignments found for course: {course_data.get('fullname')}")
        return []

    return course_data['assignments']

# Function to get submissions for a specific assignment
def get_assignment_submissions(assignment_id):
    params = {
        'wstoken': TOKEN,
        'wsfunction': 'mod_assign_get_submissions',
        'moodlewsrestformat': 'json',
        'assignmentids[0]': assignment_id
    }
    submissions = moodle_api_call(params)
    
    # Debug statement for API response
    # print("Submissions API Response:", submissions)

    if not submissions.get('assignments'):
        return []

    assignments_data = submissions.get('assignments', [])
    if not assignments_data:
        print("No assignments data returned from API.")
        return []

    assignment_data = assignments_data[0]

    if 'submissions' not in assignment_data:
        print(f"No submissions found for assignment: {assignment_id}")
        return []

    return assignment_data['submissions']

# Function to download a file from a given URL
def download_file(url):
    response = requests.get(url)
    if response.status_code == 200:
        return response.content
    else:
        raise Exception(f"Failed to download file: {response.status_code}, URL: {url}")

# Function to extract text from a PDF file
def extract_text_from_pdf(file_content):
    try:
        doc = fitz.open(stream=file_content, filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
        return text
    except Exception as e:
        return f"Error extracting text from PDF: {str(e)}"


# Function to extract text from a DOCX file
def extract_text_from_docx(file_content):
    with io.BytesIO(file_content) as f:
        doc = Document(f)
        return "\n".join([para.text for para in doc.paragraphs])

# Function to extract text from a TXT file
def extract_text_from_txt(file_content):
    return file_content.decode('utf-8')

# Function to extract text from an image file
def extract_text_from_image(file_content):
    image = Image.open(io.BytesIO(file_content))
    return pytesseract.image_to_string(image)

# Function to extract text from a submission file based on file type
def extract_text_from_submission(file):
    file_url = file['fileurl']
    file_url_with_token = f"{file_url}&token={TOKEN}" if '?' in file_url else f"{file_url}?token={TOKEN}"
    print(f"Downloading file from URL: {file_url_with_token}")  # Log the file URL
    
    file_content = download_file(file_url_with_token)
    file_name = file['filename'].lower()
    print(f"Processing file: {file_name}")  # Log the file name

    try:
        if file_name.endswith('.pdf'):
            return extract_text_from_pdf(file_content)
        elif file_name.endswith('.docx'):
            return extract_text_from_docx(file_content)
        elif file_name.endswith('.txt'):
            return extract_text_from_txt(file_content)
        elif file_name.endswith(('.png', '.jpg', '.jpeg')):
            return extract_text_from_image(file_content)
        else:
            return "Unsupported file format."
    except Exception as e:
        return f"Error extracting text: {str(e)}"


# Function to extract Q&A pairs using regex
def extract_qa_pairs(text):
    qa_pairs = re.findall(r'(Q\d+:\s.*?\nA\d+:\s.*?(?=\nQ\d+:|\Z))', text, re.DOTALL)
    if not qa_pairs:
        return [text.strip()]
    return [pair.strip() for pair in qa_pairs]

# Function to send Q&A pair to grading endpoint and get response
def grade_qa_pair(qa_pair):
    url = "http://localhost:8000/api/ollamaAGA"  # Use your actual endpoint URL
    payload = {"query": qa_pair}
    headers = {"Content-Type": "application/json"}
    
    response = requests.post(url, json=payload, headers=headers)
    
    if response.status_code == 200:
        result = response.json()
        justification = result.get("justification")
        avg_score = result.get("average_score")
        return justification, avg_score
    else:
        raise Exception(f"Failed to grade Q&A pair: {response.status_code}, Response: {response.text}")

# Function to process submissions for a single user
def process_user_submissions(user, submissions_by_user, activity_type):
    user_id = user['id']
    user_fullname = user['fullname']
    user_email = user['email']
    user_submission = submissions_by_user.get(user_id)
    
    if not user_submission:
        return {
            "Full Name": user_fullname,
            "User ID": user_id,
            "Email": user_email,
            "Total Score": 0,
            "Feedback": "No submission"
        }
    
    total_score = 0
    all_comments = []

    if activity_type == 'assignment':
        for plugin in user_submission['plugins']:
            if plugin['type'] == 'file':
                for filearea in plugin['fileareas']:
                    for file in filearea['files']:
                        try:
                            print(f"\nProcessing file: {file['filename']} for {user_fullname}...")
                            text = extract_text_from_submission(file)
                            qa_pairs = extract_qa_pairs(text)
                            
                            for i, qa_pair in enumerate(qa_pairs):
                                try:
                                    justification, avg_score = grade_qa_pair(qa_pair)
                                    total_score += avg_score
                                    comment = f"Q{i+1}: {justification}"
                                    all_comments.append(comment)

                                    print(f"  Graded Q{i+1}: Avg. Score = {avg_score:.2f} - {justification}")
                                    
                                except Exception as e:
                                    print(f"  Error grading Q&A pair {i+1} for {user_fullname}: {str(e)}")
                        except Exception as e:
                            print(f"  Error extracting text for {user_fullname}: {str(e)}")

    feedback = " | ".join(all_comments)
    return {
        "Full Name": user_fullname,
        "User ID": user_id,
        "Email": user_email,
        "Total Score": total_score,
        "Feedback": feedback
    }

# Function to get course details by ID
def get_course_by_id(course_id):
    params = {
        'wstoken': TOKEN,
        'wsfunction': 'core_course_get_courses',
        'moodlewsrestformat': 'json',
        'options[ids][0]': course_id
    }
    return moodle_api_call(params)

# Function to write data to a CSV file in Moodle-compatible format
def write_to_csv(data, course_id, assignment_name):
    filename = f"Course_{course_id}_{assignment_name.replace(' ', '_')}_autograded.csv"
    with open(filename, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        
        writer.writerow(["Full Name", "User ID", "Email", "Total Score", "Feedback"])
        
        for row in data:
            writer.writerow([row["Full Name"], row["User ID"], row["Email"], row["Total Score"], row["Feedback"]])

    print(f"Data successfully written to CSV file: {filename}")

# Function to update a user's grade in Moodle
def update_grade(user_id, assignment_id, grade, feedback):
    params = {
        'wstoken': TOKEN,
        'wsfunction': 'mod_assign_save_grade',
        'moodlewsrestformat': 'json',
        'assignmentid': assignment_id,
        'userid': user_id,
        'grade': grade,
        'feedback': feedback
    }
    response = moodle_api_call(params)
    print(f"Grade updated for User ID: {user_id}, Status: {response}")

# Main function to integrate with Moodle
# Main function to integrate with Moodle
def moodle_integration_pipeline(course_id, activity_name, activity_type):
    try:
        # Fetching course details
        print(f"\n=== Fetching Course Details for Course ID: {course_id} ===")
        course_details = get_course_by_id(course_id)
        if not course_details:
            raise Exception("Course not found.")
        course_name = course_details[0]['fullname']
        print(f"Course Name: {course_name}")

        # Fetching enrolled users
        print("\n=== Fetching Enrolled Users ===")
        users = get_enrolled_users(course_id)
        print(f"Found {len(users)} enrolled users.")

        if activity_type == 'assignment':
            # Fetching assignments
            print("\n=== Fetching Assignments ===")
            activities = get_assignments(course_id)
        else:
            raise Exception("Unsupported activity type.")

        # Debug: Print activities fetched
        # print(f"Activities fetched: {activities}")

        print(f"Found {len(activities)} {activity_type}s.")

        # Debug: Print each activity name
        # for activity in activities:
        #     print(f"Activity: {activity['name']}")

        # Matching the activity by name
        activity = next((a for a in activities if a['name'].strip().lower() == activity_name.strip().lower()), None)
        if not activity:
            raise Exception(f"{activity_type.capitalize()} not found.")

        activity_id = activity['id']
        print(f"{activity_type.capitalize()} '{activity_name}' found with ID: {activity_id}")

        # Fetching submissions for the assignment
        print("\n=== Fetching Submissions ===")
        submissions = get_assignment_submissions(activity_id)

        # Debug: Print submissions fetched
        # print(f"Submissions fetched: {submissions}")

        print(f"Found {len(submissions)} submissions.")

        submissions_by_user = {s['userid']: s for s in submissions}

        # Processing submissions
        print("\n=== Processing Submissions ===")
        processed_data = [process_user_submissions(user, submissions_by_user, activity_type) for user in users]

        # Writing data to CSV
        print("\n=== Writing Data to CSV ===")
        write_to_csv(processed_data, course_id, activity_name)

        print("\n=== Processing Completed Successfully ===")

    except Exception as e:
        print(f"\nAn error occurred: {str(e)}")

# Main function call
# course_id = 2
# activity_name = "EC1"
course_id = 245
activity_name = "Assignment 1"
activity_type = "assignment"  # Only assignment supported

moodle_integration_pipeline(course_id, activity_name, activity_type)