'''
Author:     Sai Vignesh Golla
LinkedIn:   https://www.linkedin.com/in/saivigneshgolla/

Copyright (C) 2024 Sai Vignesh Golla

License:    GNU Affero General Public License
            https://www.gnu.org/licenses/agpl-3.0.en.html
            
GitHub:     https://github.com/GodsScion/Auto_job_applier_linkedIn

Support me: https://github.com/sponsors/GodsScion

version:    26.01.20.5.08
'''


###################################################### APPLICATION INPUTS ######################################################


# >>>>>>>>>>> Easy Apply Questions & Inputs <<<<<<<<<<<

# Give an relative path of your default resume to be uploaded. If file in not found, will continue using your previously uploaded resume in LinkedIn.
default_resume_path = "resumes/senior_java.pdf"      # Default to Senior Java Developer resume

# What do you want to answer for questions that ask about years of experience you have, this is different from current_experience?
years_of_experience = "5"          # 5 years experience

# Do you need visa sponsorship now or in future?
require_visa = "Yes"               # YES - needs H1B visa sponsorship

# What is the link to your portfolio website, leave it empty as "", if you want to leave this question unanswered
website = "https://github.com/josephukeje"                        # GitHub profile

# Please provide the link to your LinkedIn profile.
linkedIn = "https://www.linkedin.com/in/josephukeje/"       # LinkedIn profile

# What is the status of your citizenship? # If left empty as "", tool will not answer the question. However, note that some companies make it compulsory to be answered
# Valid options are: "U.S. Citizen/Permanent Resident", "Non-citizen allowed to work for any employer", "Non-citizen allowed to work for current employer", "Non-citizen seeking work authorization", "Canadian Citizen/Permanent Resident" or "Other"
us_citizenship = "Non-citizen seeking work authorization"



## SOME ANNOYING QUESTIONS BY COMPANIES 🫠 ##

# What to enter in your desired salary question (American and European), What is your expected CTC (South Asian and others)?, only enter in numbers as some companies only allow numbers,
desired_salary = 1200000          # 80000, 90000, 100000 or 120000 and so on... Do NOT use quotes
'''
Note: If question has the word "lakhs" in it (Example: What is your expected CTC in lakhs), 
then it will add '.' before last 5 digits and answer. Examples: 
* 2400000 will be answered as "24.00"
* 850000 will be answered as "8.50"
And if asked in months, then it will divide by 12 and answer. Examples:
* 2400000 will be answered as "200000"
* 850000 will be answered as "70833"
'''

# What is your current CTC? Some companies make it compulsory to be answered in numbers...
current_ctc = 800000            # 800000, 900000, 1000000 or 1200000 and so on... Do NOT use quotes
'''
Note: If question has the word "lakhs" in it (Example: What is your current CTC in lakhs), 
then it will add '.' before last 5 digits and answer. Examples: 
* 2400000 will be answered as "24.00"
* 850000 will be answered as "8.50"
# And if asked in months, then it will divide by 12 and answer. Examples:
# * 2400000 will be answered as "200000"
# * 850000 will be answered as "70833"
'''

# (In Development) # Currency of salaries you mentioned. Companies that allow string inputs will add this tag to the end of numbers. Eg: 
# currency = "INR"                 # "USD", "INR", "EUR", etc.

# What is your notice period in days?
notice_period = 30                   # Any number >= 0 without quotes. Eg: 0, 7, 15, 30, 45, etc.
'''
Note: If question has 'month' or 'week' in it (Example: What is your notice period in months), 
then it will divide by 30 or 7 and answer respectively. Examples:
* For notice_period = 66:
  - "66" OR "2" if asked in months OR "9" if asked in weeks
* For notice_period = 15:"
  - "15" OR "0" if asked in months OR "2" if asked in weeks
* For notice_period = 0:
  - "0" OR "0" if asked in months OR "0" if asked in weeks
'''

# Your LinkedIn headline in quotes Eg: "Software Engineer @ Google, Masters in Computer Science", "Recent Grad Student @ MIT, Computer Science"
linkedin_headline = "Senior Java Developer | Spring Boot | Microservices | ISO 20022 | 5+ Years Experience" # "Headline" or "" to leave this question unanswered

# Your summary in quotes, use \n to add line breaks if using single quotes "Summary".You can skip \n if using triple quotes """Summary"""
linkedin_summary = """
Senior Java Developer with 5 years of hands-on experience building production-grade systems.
Experienced in Spring Boot 3.x, Spring AOP/AspectJ, Spring WebFlux, and protocol-level integrations (ISO 20022, SWIFT).
Strong foundation in Docker, Kubernetes, PostgreSQL, and observability tooling (Prometheus, Grafana).
Currently at Interswitch Germany building enterprise banking and payment platforms.
"""

'''
Note: If left empty as "", the tool will not answer the question. However, note that some companies make it compulsory to be answered. Use \n to add line breaks.
''' 

# Your cover letter in quotes, use \n to add line breaks if using single quotes "Cover Letter".You can skip \n if using triple quotes """Cover Letter""" (This question makes sense though)
cover_letter = """
Dear Hiring Manager,

I am writing to express my interest in this position. With 5 years of hands-on experience building production-grade backend systems, I am confident in my ability to contribute to your team.

Currently, I serve as a Senior Software Engineer at Interswitch Germany, where I design and build scalable microservices for enterprise banking and payment platforms. My expertise spans Java 21, Spring Boot 3.x, Node.js/TypeScript, Go, and Python, with deep experience in ISO 20022 financial messaging, Docker/Kubernetes deployments, and observability tooling.

Key highlights:
- Led ISO 20022 payment integration handling millions of transactions
- Built high-throughput Go microservices for API gateway layers
- Implemented Spring AOP cross-cutting security frameworks
- Delivered systems for Tier-1 banks with 100% Veracode compliance

I am actively seeking opportunities with visa sponsorship and am open to relocation. I would welcome the chance to discuss how my skills align with your needs.

Thank you for your consideration.

Best regards,
Joseph Ukeje
"""
##> ------ Dheeraj Deshwal : dheeraj9811 Email:dheeraj20194@iiitd.ac.in/dheerajdeshwal9811@gmail.com - Feature ------

# Your user_information_all letter in quotes, use \n to add line breaks if using single quotes "user_information_all".You can skip \n if using triple quotes """user_information_all""" (This question makes sense though)
# We use this to pass to AI to generate answer from information , Assuing Information contians eg: resume  all the information like name, experience, skills, Country, any illness etc.
user_information_all ="""
Name: Joseph Ukeje
Email: ukejejoseph1@gmail.com
Phone: +2347087232777
Location: Nigeria (Open to Remote, Open to Relocate)
Experience: 5 years

Current Role: Senior Software Engineer at Interswitch Germany (Apr 2025 - Present)

Skills:
- Languages: Java 21, TypeScript, JavaScript, Go, Solidity, C#
- Backend: Spring Boot 3.x, Spring AOP/AspectJ, Spring WebFlux, Node.js, Express.js, Gin (Go)
- Protocols: ISO 20022/SWIFT, gRPC, Netty TCP, IBM MQ, RabbitMQ
- Databases: PostgreSQL, Oracle, MongoDB, Redis
- Cloud/DevOps: AWS (EC2, EKS), Docker, Kubernetes, Jenkins, GitLab CI
- Frontend: ReactJS, Vue.js, HTML5, CSS3

Education: Bachelor of Science in Software Engineering, Babcock University (GPA: 3.93/5.00)

Certifications:
- Oracle Cloud Infrastructure DevOps & Developer Certificates
- Java SE 8 (OCA/OCP)
- CompTIA A+ (Core 1 & Core 2)
- UiPath RPA Certification

Work Authorization: Requires visa sponsorship (H1B/Work Permit)
"""
##<
'''
Note: If left empty as "", the tool will not answer the question. However, note that some companies make it compulsory to be answered. Use \n to add line breaks.
''' 

# Name of your most recent employer
recent_employer = "Interswitch" # Current employer in Germany

# Example question: "On a scale of 1-10 how much experience do you have building web or mobile applications? 1 being very little or only in school, 10 being that you have built and launched applications to real users"
confidence_level = "8"             # Any number between "1" to "10" including 1 and 10, put it in quotes ""
##



# >>>>>>>>>>> RELATED SETTINGS <<<<<<<<<<<

## Allow Manual Inputs
# Should the tool pause before every submit application during easy apply to let you check the information?
pause_before_submit = True         # True or False, Note: True or False are case-sensitive
'''
Note: Will be treated as False if `run_in_background = True`
'''

# Should the tool pause if it needs help in answering questions during easy apply?
# Note: If set as False will answer randomly...
pause_at_failed_question = True    # True or False, Note: True or False are case-sensitive
'''
Note: Will be treated as False if `run_in_background = True`
'''
##

# Do you want to overwrite previous answers?
overwrite_previous_answers = False # True or False, Note: True or False are case-sensitive







############################################################################################################
'''
THANK YOU for using my tool 😊! Wishing you the best in your job hunt 🙌🏻!

Sharing is caring! If you found this tool helpful, please share it with your peers 🥺. Your support keeps this project alive.

Support my work on <PATREON_LINK>. Together, we can help more job seekers.

As an independent developer, I pour my heart and soul into creating tools like this, driven by the genuine desire to make a positive impact.

Your support, whether through donations big or small or simply spreading the word, means the world to me and helps keep this project alive and thriving.

Gratefully yours 🙏🏻,
Sai Vignesh Golla
'''
############################################################################################################