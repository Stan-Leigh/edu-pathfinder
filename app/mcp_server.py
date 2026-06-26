from mcp.server.fastmcp import FastMCP

mcp = FastMCP("edu-pathfinder-server")

@mcp.tool()
def get_tutors_by_subject(subject: str) -> str:
    """Find available free tutors and peer mentoring groups for a specific subject.
    
    Args:
        subject: The subject name (e.g. Math, Science, English, History).
    """
    subject_lower = subject.lower()
    if "math" in subject_lower:
        return (
            "Available Math Tutors:\n"
            "- Sarah Jenkins (Calculus & Algebra) - Rating: 4.9/5 - Availability: Mon/Wed 4-6 PM\n"
            "- David Chen (Geometry & Trigonometry) - Rating: 4.8/5 - Availability: Tue/Thu 3-5 PM\n"
            "- Peer Mentoring Group: Math Olympiad Club - Every Saturday 10 AM (Free)"
        )
    elif "science" in subject_lower or "physics" in subject_lower or "chemistry" in subject_lower:
        return (
            "Available Science Tutors:\n"
            "- Dr. Robert Carter (Physics & Chemistry) - Rating: 5.0/5 - Availability: Mon/Fri 5-7 PM\n"
            "- Elena Rostova (Biology) - Rating: 4.7/5 - Availability: Wed/Thu 4-6 PM\n"
            "- Science Lab Peer Study Circle - Every Sunday 2 PM (Free)"
        )
    else:
        return (
            f"Available General Tutors for {subject}:\n"
            f"- Liam O'Connor (General Education) - Rating: 4.8/5 - Availability: Mon-Thu 4-5 PM\n"
            f"- Sophia Martinez (Literacy & Writing) - Rating: 4.9/5 - Availability: Tue/Fri 3-6 PM\n"
            f"- Peer Help Desk - Daily 3-6 PM (Free)"
        )

@mcp.tool()
def get_study_resources(topic: str, grade_level: str) -> str:
    """Retrieve open-source study guides, textbooks, and practice exercises for a topic and grade level.
    
    Args:
        topic: Specific study topic (e.g. quadratic equations, photosynthesis, essay writing).
        grade_level: Target student grade level (e.g. Grade 8, Grade 10, Undergraduate).
    """
    return (
        f"Curated Open Educational Resources (OER) for {topic} ({grade_level}):\n"
        f"1. OpenStax Interactive Textbook Chapter: '{topic.title()}' - Free PDF & Web access.\n"
        f"2. Khan Academy Exercise Suite: '{topic.title()} Practice' - Video tutorials + 10 interactive worksheets.\n"
        f"3. CK-12 FlexBook Resource: '{topic.title()} Concept Exploration' - Simulation games and quizzes.\n"
        f"4. CrashCourse YouTube Study Companion Guide for {topic.title()}."
    )

@mcp.tool()
def log_study_progress(student_id: str, subject: str, units_completed: int, hours_spent: float) -> str:
    """Log student learning progress, including completed units and study time, to the progress tracking system.
    
    Args:
        student_id: Unique student ID (e.g. SID-99321).
        subject: The subject being studied.
        units_completed: Number of learning units or chapters finished in this session.
        hours_spent: Number of hours dedicated to studying in this session.
    """
    return (
        f"Progress logged successfully for Student {student_id}:\n"
        f"- Subject: {subject}\n"
        f"- Units Completed: +{units_completed}\n"
        f"- Time Added: {hours_spent} hours\n"
        f"- Status: Active | Target on-track."
    )

if __name__ == "__main__":
    mcp.run()
