"""
PDF Report Generator Service
Generates comprehensive PDF interview feedback reports using ReportLab
"""
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, 
    Spacer, PageBreak, Image, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfgen import canvas
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics import renderPDF
from datetime import datetime
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class PDFReportGenerator:
    """Generate PDF interview feedback reports"""
    
    def __init__(self):
        """Initialize PDF generator"""
        self.page_width, self.page_height = letter
        self.styles = getSampleStyleSheet()
        self._create_custom_styles()
    
    def _create_custom_styles(self):
        """Create custom paragraph styles"""
        # Title style
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#4F46E5'),
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        ))
        
        # Subtitle style
        self.styles.add(ParagraphStyle(
            name='CustomSubtitle',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#6B7280'),
            spaceAfter=20,
            alignment=TA_CENTER
        ))
        
        # Section heading
        self.styles.add(ParagraphStyle(
            name='SectionHeading',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#1F2937'),
            spaceAfter=12,
            spaceBefore=12,
            fontName='Helvetica-Bold',
            borderWidth=0,
            borderColor=colors.HexColor('#4F46E5'),
            borderPadding=5,
            backColor=colors.HexColor('#F3F4F6')
        ))
        
        # Body text
        self.styles.add(ParagraphStyle(
            name='CustomBody',
            parent=self.styles['Normal'],
            fontSize=11,
            leading=16,
            alignment=TA_JUSTIFY,
            spaceAfter=10
        ))
        
        # List item
        self.styles.add(ParagraphStyle(
            name='ListItem',
            parent=self.styles['Normal'],
            fontSize=10,
            leading=14,
            leftIndent=20,
            bulletIndent=10,
            spaceAfter=8
        ))
    
    def generate_report(self, session, report, output_path):
        """
        Generate complete PDF report
        
        Args:
            session: InterviewSession instance
            report: FeedbackReport instance
            output_path: Path where PDF will be saved
            
        Returns:
            str: Path to generated PDF
        """
        try:
            logger.info(f"Generating PDF report for session {session.session_id}")
            
            # Create PDF document
            doc = SimpleDocTemplate(
                str(output_path),
                pagesize=letter,
                rightMargin=0.75*inch,
                leftMargin=0.75*inch,
                topMargin=0.75*inch,
                bottomMargin=0.75*inch,
                title=f"Interview Feedback - {session.job_role.role_name}",
                author="Vocal View AI"
            )
            
            # Build content
            story = []
            
            # Add header
            story.extend(self._create_header(session, report))
            
            # Add overall scores section
            story.extend(self._create_scores_section(report))
            
            # Add summary
            story.extend(self._create_summary_section(report))
            
            # Add strengths and improvements
            story.extend(self._create_strengths_section(report))
            story.extend(self._create_improvements_section(report))
            
            # Add question-by-question analysis
            story.extend(self._create_questions_section(session))
            
            # Add recommendations
            story.extend(self._create_recommendations_section(report))
            
            # Add footer
            story.extend(self._create_footer())
            
            # Build PDF
            doc.build(story, onFirstPage=self._add_page_number, 
                     onLaterPages=self._add_page_number)
            
            logger.info(f"PDF report generated successfully: {output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Failed to generate PDF report: {str(e)}")
            raise
    
    def _create_header(self, session, report):
        """Create report header"""
        elements = []
        
        # Title
        title = Paragraph("INTERVIEW FEEDBACK REPORT", self.styles['CustomTitle'])
        elements.append(title)
        
        # Subtitle with job role
        subtitle = Paragraph(
            f"{session.job_role.role_name}",
            self.styles['CustomSubtitle']
        )
        elements.append(subtitle)
        
        # Interview details table
        details_data = [
            ['Candidate:', session.user.username],
            ['Date:', session.created_at.strftime('%B %d, %Y')],
            ['Duration:', f"{session.duration_minutes:.1f} minutes"],
            ['Questions:', str(session.questions.count())],
        ]
        
        details_table = Table(details_data, colWidths=[1.5*inch, 4*inch])
        details_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#6B7280')),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(details_table)
        elements.append(Spacer(1, 0.3*inch))
        
        return elements
    
    def _create_scores_section(self, report):
        """Create overall scores section with visual chart"""
        elements = []
        
        # Section heading
        heading = Paragraph("Performance Overview", self.styles['SectionHeading'])
        elements.append(heading)
        elements.append(Spacer(1, 0.1*inch))
        
        # Overall score - large display
        overall_score_data = [[
            Paragraph(
                f"<b><font size=36 color='#4F46E5'>{report.overall_score:.0f}%</font></b>",
                self.styles['CustomBody']
            )
        ]]
        overall_table = Table(overall_score_data, colWidths=[6.5*inch])
        overall_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F3F4F6')),
            ('TOPPADDING', (0, 0), (-1, -1), 15),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
        ]))
        elements.append(overall_table)
        elements.append(Spacer(1, 0.2*inch))
        
        # Component scores table
        scores_data = [
            ['Metric', 'Score', 'Rating'],
            ['Content Quality', f"{report.content_score:.1f}%", self._get_rating(report.content_score)],
            ['Delivery & Speech', f"{report.delivery_score:.1f}%", self._get_rating(report.delivery_score)],
            ['Confidence Level', f"{report.confidence_score:.1f}%", self._get_rating(report.confidence_score)],
        ]
        
        scores_table = Table(scores_data, colWidths=[2.5*inch, 2*inch, 2*inch])
        scores_table.setStyle(TableStyle([
            # Header row
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4F46E5')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            
            # Data rows
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E5E7EB')),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            
            # Alternating row colors
            ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#F9FAFB')),
            ('BACKGROUND', (0, 3), (-1, 3), colors.HexColor('#F9FAFB')),
        ]))
        elements.append(scores_table)
        elements.append(Spacer(1, 0.3*inch))
        
        return elements
    
    def _get_rating(self, score):
        """Get text rating from score"""
        if score >= 80:
            return "Excellent"
        elif score >= 70:
            return "Good"
        elif score >= 60:
            return "Fair"
        else:
            return "Needs Work"
    
    def _create_summary_section(self, report):
        """Create summary feedback section"""
        elements = []
        
        heading = Paragraph("Executive Summary", self.styles['SectionHeading'])
        elements.append(heading)
        
        summary = Paragraph(report.summary_feedback, self.styles['CustomBody'])
        elements.append(summary)
        elements.append(Spacer(1, 0.2*inch))
        
        return elements
    
    def _create_strengths_section(self, report):
        """Create strengths section"""
        elements = []
        
        heading = Paragraph("Key Strengths", self.styles['SectionHeading'])
        elements.append(heading)
        
        if report.strengths:
            for strength in report.strengths:
                bullet = Paragraph(
                    f"• {strength}",
                    self.styles['ListItem']
                )
                elements.append(bullet)
        else:
            text = Paragraph("Continue practicing to identify your strengths.", 
                           self.styles['CustomBody'])
            elements.append(text)
        
        elements.append(Spacer(1, 0.2*inch))
        return elements
    
    def _create_improvements_section(self, report):
        """Create areas for improvement section"""
        elements = []
        
        heading = Paragraph("Areas for Improvement", self.styles['SectionHeading'])
        elements.append(heading)
        
        if report.areas_for_improvement:
            for improvement in report.areas_for_improvement:
                bullet = Paragraph(
                    f"• {improvement}",
                    self.styles['ListItem']
                )
                elements.append(bullet)
        else:
            text = Paragraph("Great work! Keep up the excellent performance.", 
                           self.styles['CustomBody'])
            elements.append(text)
        
        elements.append(Spacer(1, 0.2*inch))
        return elements
    
    def _create_questions_section(self, session):
        """Create question-by-question analysis"""
        elements = []
        
        heading = Paragraph("Detailed Question Analysis", self.styles['SectionHeading'])
        elements.append(heading)
        elements.append(Spacer(1, 0.1*inch))
        
        for idx, answer in enumerate(session.answers.all(), 1):
            # Question header
            q_header = Paragraph(
                f"<b>Question {idx}:</b> {answer.question.question_text}",
                self.styles['CustomBody']
            )
            elements.append(q_header)
            elements.append(Spacer(1, 0.05*inch))
            
            # Answer transcription (truncated)
            if answer.transcribed_text:
                transcription = answer.transcribed_text[:200]
                if len(answer.transcribed_text) > 200:
                    transcription += "..."
                
                trans_text = Paragraph(
                    f"<i>Your answer: {transcription}</i>",
                    self.styles['CustomBody']
                )
                elements.append(trans_text)
                elements.append(Spacer(1, 0.05*inch))
            
            # Analysis metrics
            metrics_data = []
            
            if hasattr(answer, 'content_analysis'):
                content = answer.content_analysis
                metrics_data.append(['Relevance', f"{content.relevance_score:.0f}%"])
                metrics_data.append(['Clarity', f"{content.clarity_score:.0f}%"])
                metrics_data.append(['Filler Words', str(content.filler_word_count)])
                metrics_data.append(['Word Count', str(content.word_count)])
            
            if hasattr(answer, 'prosody_analysis'):
                prosody = answer.prosody_analysis
                metrics_data.append(['Speaking Pace', f"{prosody.speaking_pace_wpm:.0f} WPM"])
            
            if hasattr(answer, 'facial_analysis'):
                facial = answer.facial_analysis
                metrics_data.append(['Confidence', f"{facial.confidence_score:.0f}%"])
            
            if metrics_data:
                metrics_table = Table(metrics_data, colWidths=[2*inch, 2*inch])
                metrics_table.setStyle(TableStyle([
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#6B7280')),
                    ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E5E7EB')),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ]))
                elements.append(metrics_table)
            
            elements.append(Spacer(1, 0.15*inch))
        
        return elements
    
    def _create_recommendations_section(self, report):
        """Create recommendations section"""
        elements = []
        
        heading = Paragraph("Recommendations for Success", self.styles['SectionHeading'])
        elements.append(heading)
        
        recommendations = [
            "Practice the STAR method (Situation, Task, Action, Result) for behavioral questions",
            "Maintain consistent eye contact with the camera to show confidence",
            "Reduce filler words by pausing briefly to collect your thoughts",
            "Speak at a moderate pace (120-150 words per minute) for clarity",
            "Prepare specific examples from your experience before interviews",
            "Research the company and role thoroughly before interviewing",
        ]
        
        for rec in recommendations:
            bullet = Paragraph(f"• {rec}", self.styles['ListItem'])
            elements.append(bullet)
        
        elements.append(Spacer(1, 0.2*inch))
        return elements
    
    def _create_footer(self):
        """Create report footer"""
        elements = []
        
        elements.append(Spacer(1, 0.3*inch))
        
        footer_text = Paragraph(
            "<i>This report was generated by Vocal View AI - Virtual Interview Coach<br/>"
            "University of Mianwali © 2024</i>",
            ParagraphStyle(
                'Footer',
                parent=self.styles['Normal'],
                fontSize=8,
                textColor=colors.HexColor('#9CA3AF'),
                alignment=TA_CENTER
            )
        )
        elements.append(footer_text)
        
        return elements
    
    def _add_page_number(self, canvas, doc):
        """Add page numbers to each page"""
        page_num = canvas.getPageNumber()
        text = f"Page {page_num}"
        canvas.setFont('Helvetica', 9)
        canvas.setFillColor(colors.HexColor('#9CA3AF'))
        canvas.drawRightString(
            doc.pagesize[0] - 0.75*inch,
            0.5*inch,
            text
        )


# Singleton instance
_pdf_generator = None

def get_pdf_generator():
    """Get singleton instance of PDFReportGenerator"""
    global _pdf_generator
    if _pdf_generator is None:
        _pdf_generator = PDFReportGenerator()
    return _pdf_generator