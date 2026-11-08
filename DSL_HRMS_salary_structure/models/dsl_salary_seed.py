# -*- coding: utf-8 -*-
from odoo import api, models

LEGACY_CODE_RENAME_MAP = {
    'MED': 'MEDICAL',
    'CONV': 'CONVEYANCE',
    'DEARNESS': 'DEARNESS_ALLOWANCE',
    'TECH_SKILL': 'TECHNICAL',
    'HARDSHIP': 'HARD_TO_REACH',
    'ATT_BON': 'ATTENDANCE_BONUS',
    'PROD_INC': 'PRODUCTION_BONUS',
    'OT': 'OVERTIME',
    'NIGHT': 'NIGHT_SHIFT',
    'FEST_BON': 'FESTIVAL_BONUS',
    'TDS': 'INCOME_TAX',
    'PF_EMP': 'PF_EMPLOYEE',
    'LWP_DED': 'UNPAID_LEAVE',
    'LATE_DED': 'LATE_ADJUSTMENT',
    'WELFARE': 'WELFARE_FUND',
    'GROUP_INS': 'INSURANCE_EMPLOYEE',
    'TRANS_DED': 'TRANSPORT_RECOVERY',
    'LUNCH_DED': 'FOOD_RECOVERY',
    'ACCOM_DED': 'HOUSE_RENT_RECOVERY',
    'LOAN_ADV': 'LOAN',
    'DAMAGE_FINE': 'DAMAGE_RECOVERY',
}

# Tuple format:
# (seq, code, name, name_bn, category, sub_group, calc_type, amount, pct, based_on, taxable, tax_treat, pf, ot, bonus, recurring, prorated, approval_req, acc_code)
BD_COMPLETE_SALARY_CATALOG = [
    # =========================================================================
    # 1. Basic Salary & Regular Allowances (15)
    # =========================================================================
    (10, 'BASIC', 'Basic Salary', 'মূল বেতন', 'basic', '1. Basic & Regular Allowances', 'percentage', 0.0, 50.0, 'gross', True, 'fully_taxable', True, True, True, True, True, False, '510101'),
    (12, 'HRA', 'House Rent Allowance', 'বাড়ি ভাড়া ভাতা', 'allowance', '1. Basic & Regular Allowances', 'percentage', 0.0, 25.0, 'gross', True, 'fully_taxable', False, False, False, True, True, False, '510102'),
    (14, 'MEDICAL', 'Medical Allowance', 'চিকিৎসা ভাতা', 'allowance', '1. Basic & Regular Allowances', 'percentage', 0.0, 10.0, 'gross', True, 'fully_taxable', False, False, False, True, True, False, '510103'),
    (16, 'CONVEYANCE', 'Conveyance Allowance', 'যাতায়াত ভাতা', 'allowance', '1. Basic & Regular Allowances', 'percentage', 0.0, 10.0, 'gross', True, 'fully_taxable', False, False, False, True, True, False, '510104'),
    (18, 'TRANSPORT', 'Transport Allowance', 'পরিবহন ভাতা', 'allowance', '1. Basic & Regular Allowances', 'fixed', 2500.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, True, True, False, '510105'),
    (20, 'DEARNESS_ALLOWANCE', 'Dearness Allowance', 'মহার্ঘ ভাতা', 'allowance', '1. Basic & Regular Allowances', 'percentage', 0.0, 10.0, 'basic', True, 'fully_taxable', False, False, False, True, True, False, '510106'),
    (22, 'SPECIAL', 'Special Allowance', 'বিশেষ ভাতা', 'allowance', '1. Basic & Regular Allowances', 'percentage', 0.0, 5.0, 'gross', True, 'fully_taxable', False, False, False, True, True, False, '510107'),
    (24, 'PERSONAL', 'Personal Allowance', 'ব্যক্তিগত ভাতা', 'allowance', '1. Basic & Regular Allowances', 'fixed', 2000.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, True, True, False, '510108'),
    (26, 'ADDITIONAL', 'Additional Allowance', 'অতিরিক্ত ভাতা', 'allowance', '1. Basic & Regular Allowances', 'fixed', 1500.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, True, True, False, '510109'),
    (28, 'COST_OF_LIVING', 'Cost of Living Allowance', 'জীবনযাত্রার ব্যয় ভাতা', 'allowance', '1. Basic & Regular Allowances', 'percentage', 0.0, 10.0, 'basic', True, 'fully_taxable', False, False, False, True, True, False, '510110'),
    (30, 'ADJUSTMENT', 'Salary Adjustment', 'বেতন সমন্বয়', 'allowance', '1. Basic & Regular Allowances', 'fixed', 0.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, False, False, False, '510111'),
    (31, 'CAR_FUEL', 'Car, Fuel & Maintenance Allowance', 'গাড়ি ও জ্বালানি ভাতা', 'allowance', '1. Basic & Regular Allowances', 'fixed', 15000.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, True, False, False, '510112'),
    (32, 'CITY_ALLOW', 'City Compensatory Allowance', 'মহানগর ভাতা', 'allowance', '1. Basic & Regular Allowances', 'fixed', 2000.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, True, True, False, '510113'),
    (33, 'EDU_ALLOW', 'Children Education Allowance', 'সন্তানের শিক্ষা সহায়তা ভাতা', 'allowance', '1. Basic & Regular Allowances', 'fixed', 2000.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, True, False, False, '510114'),
    (34, 'ENT_EXEC', 'Executive Entertainment Allowance', 'নির্বাহী আপ্যায়ন ভাতা', 'allowance', '1. Basic & Regular Allowances', 'fixed', 5000.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, True, False, False, '510115'),

    # =========================================================================
    # 2. Food, Daily & Communication Allowances (11)
    # =========================================================================
    (40, 'FOOD', 'Food Allowance', 'খাবার ভাতা', 'allowance', '2. Food & Daily Allowances', 'fixed', 1250.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, True, True, False, '510201'),
    (41, 'LUNCH', 'Lunch Allowance', 'দুপুরের খাবার ভাতা', 'allowance', '2. Food & Daily Allowances', 'fixed', 1500.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, True, True, False, '510202'),
    (42, 'DINNER', 'Dinner Allowance', 'রাতের খাবার ভাতা', 'allowance', '2. Food & Daily Allowances', 'fixed', 1000.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, True, True, False, '510203'),
    (43, 'BREAKFAST', 'Breakfast Allowance', 'সকালের নাশতা ভাতা', 'allowance', '2. Food & Daily Allowances', 'fixed', 800.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, True, True, False, '510204'),
    (44, 'TIFFIN', 'Tiffin Allowance', 'টিফিন ভাতা', 'allowance', '2. Food & Daily Allowances', 'fixed', 1000.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, True, True, False, '510205'),
    (45, 'SNACKS', 'Snacks Allowance', 'নাশতা ভাতা', 'allowance', '2. Food & Daily Allowances', 'fixed', 600.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, True, True, False, '510206'),
    (46, 'MEAL', 'Meal Allowance', 'খাবার সংক্রান্ত ভাতা', 'allowance', '2. Food & Daily Allowances', 'fixed', 1500.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, True, True, False, '510207'),
    (47, 'MOBILE', 'Mobile Allowance', 'মোবাইল বিল ভাতা', 'allowance', '2. Food & Daily Allowances', 'fixed', 1000.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, True, False, False, '510208'),
    (48, 'INTERNET', 'Internet Allowance', 'ইন্টারনেট ভাতা', 'allowance', '2. Food & Daily Allowances', 'fixed', 1000.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, True, False, False, '510209'),
    (49, 'PHONE', 'Telephone Allowance', 'টেলিফোন ভাতা', 'allowance', '2. Food & Daily Allowances', 'fixed', 800.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, True, False, False, '510210'),
    (50, 'UTILITY', 'Utility Allowance', 'বিদ্যুৎ, গ্যাস ও অন্যান্য ইউটিলিটি ভাতা', 'allowance', '2. Food & Daily Allowances', 'fixed', 2500.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, True, False, False, '510211'),

    # =========================================================================
    # 3. Festival, Annual & Special Allowances (13)
    # =========================================================================
    (60, 'EID_BONUS_1', 'First Eid Bonus (Eid-ul-Fitr)', 'প্রথম ঈদ বোনাস', 'bonus_incentive', '3. Festival & Annual Allowances', 'percentage', 0.0, 100.0, 'basic', True, 'fully_taxable', False, False, False, False, False, False, '510301'),
    (61, 'EID_BONUS_2', 'Second Eid Bonus (Eid-ul-Adha)', 'দ্বিতীয় ঈদ বোনাস', 'bonus_incentive', '3. Festival & Annual Allowances', 'percentage', 0.0, 100.0, 'basic', True, 'fully_taxable', False, False, False, False, False, False, '510302'),
    (62, 'DURGA_BONUS', 'Durga Puja Bonus', 'দুর্গাপূজা বোনাস', 'bonus_incentive', '3. Festival & Annual Allowances', 'percentage', 0.0, 100.0, 'basic', True, 'fully_taxable', False, False, False, False, False, False, '510303'),
    (63, 'FESTIVAL_BONUS', 'Festival Bonus', 'উৎসব বোনাস', 'bonus_incentive', '3. Festival & Annual Allowances', 'percentage', 0.0, 100.0, 'basic', True, 'fully_taxable', False, False, False, False, False, False, '510304'),
    (64, 'BOISHAKHI', 'Boishakhi Allowance', 'বৈশাখী ভাতা', 'bonus_incentive', '3. Festival & Annual Allowances', 'percentage', 0.0, 20.0, 'basic', True, 'fully_taxable', False, False, False, False, False, False, '510305'),
    (65, 'NEW_YEAR', 'New Year Allowance', 'নববর্ষ ভাতা', 'bonus_incentive', '3. Festival & Annual Allowances', 'fixed', 2000.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, False, False, False, '510306'),
    (66, 'ANNUAL_BONUS', 'Annual Bonus', 'বার্ষিক বোনাস', 'bonus_incentive', '3. Festival & Annual Allowances', 'percentage', 0.0, 100.0, 'basic', True, 'fully_taxable', False, False, False, False, False, False, '510307'),
    (67, 'SPECIAL_BONUS', 'Special Bonus', 'বিশেষ বোনাস', 'bonus_incentive', '3. Festival & Annual Allowances', 'fixed', 5000.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, False, False, False, '510308'),
    (68, 'EX_GRATIA', 'Ex-gratia Payment', 'অনুগ্রহমূলক অর্থ প্রদান', 'bonus_incentive', '3. Festival & Annual Allowances', 'fixed', 0.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, False, False, False, '510309'),
    (69, 'LEAVE_ENCASHMENT', 'Leave Encashment', 'ছুটির পরিবর্তে অর্থ', 'bonus_incentive', '3. Festival & Annual Allowances', 'fixed', 0.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, False, False, False, '510310'),
    (70, 'LFA', 'Leave Fare Assistance (LFA)', 'লিভ ফেয়ার অ্যাসিস্ট্যান্স', 'bonus_incentive', '3. Festival & Annual Allowances', 'percentage', 0.0, 50.0, 'basic', True, 'fully_taxable', False, False, False, False, False, False, '510311'),
    (71, 'ARREAR', 'Salary Arrear', 'বকেয়া বেতন', 'bonus_incentive', '3. Festival & Annual Allowances', 'fixed', 0.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, False, False, False, '510312'),
    (72, 'INCREMENT_ARREAR', 'Increment Arrear', 'ইনক্রিমেন্টের বকেয়া', 'bonus_incentive', '3. Festival & Annual Allowances', 'fixed', 0.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, False, False, False, '510313'),

    # =========================================================================
    # 4. Performance & Productivity Allowances (14)
    # =========================================================================
    (80, 'PERFORMANCE', 'Performance Allowance', 'কর্মদক্ষতা ভাতা', 'bonus_incentive', '4. Performance & Productivity', 'fixed', 3000.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, True, False, False, '510401'),
    (81, 'KPI_BONUS', 'KPI Bonus', 'KPI অর্জন বোনাস', 'bonus_incentive', '4. Performance & Productivity', 'fixed', 5000.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, False, False, False, '510402'),
    (82, 'TARGET_BONUS', 'Target Achievement Bonus', 'লক্ষ্যমাত্রা অর্জন বোনাস', 'bonus_incentive', '4. Performance & Productivity', 'fixed', 5000.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, False, False, False, '510403'),
    (83, 'SALES_COMMISSION', 'Sales Commission', 'বিক্রয় কমিশন', 'bonus_incentive', '4. Performance & Productivity', 'fixed', 0.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, False, False, False, '510404'),
    (84, 'SALES_BONUS', 'Sales Bonus', 'বিক্রয় বোনাস', 'bonus_incentive', '4. Performance & Productivity', 'fixed', 0.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, False, False, False, '510405'),
    (85, 'PRODUCTION_BONUS', 'Production Bonus', 'উৎপাদন বোনাস', 'bonus_incentive', '4. Performance & Productivity', 'fixed', 1500.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, True, False, False, '510406'),
    (86, 'ATTENDANCE_BONUS', 'Attendance Bonus', 'উপস্থিতি বোনাস', 'bonus_incentive', '4. Performance & Productivity', 'fixed', 750.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, True, False, False, '510407'),
    (87, 'PUNCTUALITY_BONUS', 'Punctuality Bonus', 'সময়ানুবর্তিতা বোনাস', 'bonus_incentive', '4. Performance & Productivity', 'fixed', 500.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, True, False, False, '510408'),
    (88, 'QUALITY_BONUS', 'Quality Bonus', 'মান নিয়ন্ত্রণ বোনাস', 'bonus_incentive', '4. Performance & Productivity', 'fixed', 1000.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, True, False, False, '510409'),
    (89, 'PROJECT_BONUS', 'Project Completion Bonus', 'প্রকল্প সম্পন্ন বোনাস', 'bonus_incentive', '4. Performance & Productivity', 'fixed', 0.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, False, False, False, '510410'),
    (90, 'TEAM_BONUS', 'Team Performance Bonus', 'দলীয় কর্মদক্ষতা বোনাস', 'bonus_incentive', '4. Performance & Productivity', 'fixed', 0.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, False, False, False, '510411'),
    (91, 'PROFIT_SHARING', 'Profit Sharing (WPPF)', 'মুনাফা বণ্টন', 'bonus_incentive', '4. Performance & Productivity', 'fixed', 0.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, False, False, False, '510412'),
    (92, 'INCENTIVE', 'Incentive', 'প্রণোদনা', 'bonus_incentive', '4. Performance & Productivity', 'fixed', 2000.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, False, False, False, '510413'),
    (93, 'REWARD', 'Reward', 'পুরস্কার', 'bonus_incentive', '4. Performance & Productivity', 'fixed', 0.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, False, False, False, '510414'),

    # =========================================================================
    # 5. Overtime, Shift & Work Allowances (11)
    # =========================================================================
    (100, 'OVERTIME', 'Overtime Allowance (BD 2x Basic)', 'অতিরিক্ত কাজের পারিশ্রমিক', 'overtime_variable', '5. Overtime, Shift & Work', 'formula', 0.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, False, False, False, '510501'),
    (101, 'HOLIDAY_WORK', 'Holiday Work Allowance', 'ছুটির দিনে কাজের পারিশ্রমিক', 'overtime_variable', '5. Overtime, Shift & Work', 'fixed', 0.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, False, False, False, '510502'),
    (102, 'WEEKEND_WORK', 'Weekend Work Allowance', 'সাপ্তাহিক ছুটিতে কাজের পারিশ্রমিক', 'overtime_variable', '5. Overtime, Shift & Work', 'fixed', 0.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, False, False, False, '510503'),
    (103, 'NIGHT_SHIFT', 'Night Shift Allowance', 'নাইট শিফট ভাতা', 'overtime_variable', '5. Overtime, Shift & Work', 'fixed', 0.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, False, False, False, '510504'),
    (104, 'EVENING_SHIFT', 'Evening Shift Allowance', 'সন্ধ্যা শিফট ভাতা', 'overtime_variable', '5. Overtime, Shift & Work', 'fixed', 0.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, False, False, False, '510505'),
    (105, 'ROTATIONAL_SHIFT', 'Rotational Shift Allowance', 'রোটেশনাল শিফট ভাতা', 'overtime_variable', '5. Overtime, Shift & Work', 'fixed', 1500.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, True, False, False, '510506'),
    (106, 'SHIFT_ALLOWANCE', 'Shift Allowance', 'শিফট ভাতা', 'overtime_variable', '5. Overtime, Shift & Work', 'fixed', 1000.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, True, False, False, '510507'),
    (107, 'EMERGENCY_DUTY', 'Emergency Duty Allowance', 'জরুরি দায়িত্ব ভাতা', 'overtime_variable', '5. Overtime, Shift & Work', 'fixed', 1000.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, False, False, False, '510508'),
    (108, 'ON_CALL', 'On-call Allowance', 'অন-কল ভাতা', 'overtime_variable', '5. Overtime, Shift & Work', 'fixed', 2000.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, True, False, False, '510509'),
    (109, 'STANDBY', 'Standby Allowance', 'প্রস্তুতিমূলক দায়িত্ব ভাতা', 'overtime_variable', '5. Overtime, Shift & Work', 'fixed', 1500.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, True, False, False, '510510'),
    (110, 'HOLIDAY_ALLOWANCE', 'Holiday Allowance', 'ছুটির দিনের ভাতা', 'overtime_variable', '5. Overtime, Shift & Work', 'fixed', 1000.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, False, False, False, '510511'),

    # =========================================================================
    # 6. Position, Responsibility & Professional Allowances (13)
    # =========================================================================
    (115, 'HOUSEKEEPING', 'Housekeeping Allowance', 'গৃহস্থালি সহায়তা ভাতা', 'allowance', '6. Position & Professional', 'fixed', 3000.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, True, False, False, '510601'),
    (116, 'DRIVER', 'Driver Allowance', 'গাড়িচালক ভাতা', 'allowance', '6. Position & Professional', 'fixed', 12000.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, True, False, False, '510602'),
    (117, 'SUPPORT_STAFF', 'Support Staff Allowance', 'সহায়ক কর্মী ভাতা', 'allowance', '6. Position & Professional', 'fixed', 2500.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, True, False, False, '510603'),
    (118, 'RESPONSIBILITY', 'Responsibility Allowance', 'দায়িত্ব ভাতা', 'allowance', '6. Position & Professional', 'fixed', 3000.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, True, True, False, '510604'),
    (119, 'ACTING', 'Acting Allowance', 'ভারপ্রাপ্ত দায়িত্ব ভাতা', 'allowance', '6. Position & Professional', 'percentage', 0.0, 10.0, 'basic', True, 'fully_taxable', False, False, False, True, True, False, '510605'),
    (120, 'CHARGE', 'Charge Allowance', 'অতিরিক্ত দায়িত্ব গ্রহণ ভাতা', 'allowance', '6. Position & Professional', 'percentage', 0.0, 10.0, 'basic', True, 'fully_taxable', False, False, False, True, True, False, '510606'),
    (121, 'TECHNICAL', 'Technical Allowance', 'কারিগরি ভাতা', 'allowance', '6. Position & Professional', 'fixed', 3000.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, True, True, False, '510607'),
    (122, 'PROFESSIONAL', 'Professional Allowance', 'পেশাগত ভাতা', 'allowance', '6. Position & Professional', 'fixed', 5000.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, True, True, False, '510608'),
    (123, 'CERTIFICATION', 'Certification Allowance', 'পেশাগত সনদ ভাতা', 'allowance', '6. Position & Professional', 'fixed', 3000.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, True, False, False, '510609'),
    (124, 'LANGUAGE', 'Language Allowance', 'ভাষাগত দক্ষতা ভাতা', 'allowance', '6. Position & Professional', 'fixed', 2000.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, True, False, False, '510610'),
    (125, 'QUALIFICATION', 'Qualification Allowance', 'শিক্ষাগত যোগ্যতা ভাতা', 'allowance', '6. Position & Professional', 'fixed', 2500.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, True, False, False, '510611'),
    (126, 'RISK', 'Risk Allowance', 'ঝুঁকি ভাতা', 'allowance', '6. Position & Professional', 'fixed', 2000.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, True, True, False, '510612'),
    (127, 'HARD_TO_REACH', 'Hardship Allowance', 'দুর্গম এলাকায় কাজের ভাতা', 'allowance', '6. Position & Professional', 'fixed', 3000.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, True, True, False, '510613'),

    # =========================================================================
    # 7. Travel, Field & Project Allowances (13 — Unique DAILY_ALLOWANCE!)
    # =========================================================================
    (130, 'TRAVEL', 'Travel Allowance', 'ভ্রমণ ভাতা', 'allowance', '7. Travel, Field & Project', 'fixed', 2000.0, 0.0, 'basic', False, 'non_taxable_reimbursement', False, False, False, False, False, False, '510701'),
    (131, 'DAILY_ALLOWANCE', 'Daily Allowance (DA)', 'দৈনিক ভাতা', 'allowance', '7. Travel, Field & Project', 'fixed', 1000.0, 0.0, 'basic', False, 'non_taxable_reimbursement', False, False, False, False, False, False, '510702'),
    (132, 'TA', 'Travelling Allowance (TA)', 'যাতায়াত খরচ ভাতা', 'allowance', '7. Travel, Field & Project', 'fixed', 1500.0, 0.0, 'basic', False, 'non_taxable_reimbursement', False, False, False, False, False, False, '510703'),
    (133, 'FA', 'Field Allowance', 'মাঠপর্যায়ের কাজের ভাতা', 'allowance', '7. Travel, Field & Project', 'fixed', 2500.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, True, True, False, '510704'),
    (134, 'SITE', 'Site Allowance', 'সাইট ভাতা', 'allowance', '7. Travel, Field & Project', 'fixed', 3000.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, True, True, False, '510705'),
    (135, 'TOUR', 'Tour Allowance', 'ট্যুর ভাতা', 'allowance', '7. Travel, Field & Project', 'fixed', 0.0, 0.0, 'basic', False, 'non_taxable_reimbursement', False, False, False, False, False, False, '510706'),
    (136, 'PROJECT_TRAVEL', 'Project Travel Allowance', 'প্রকল্প ভ্রমণ ভাতা', 'allowance', '7. Travel, Field & Project', 'fixed', 0.0, 0.0, 'basic', False, 'non_taxable_reimbursement', False, False, False, False, False, False, '510707'),
    (137, 'OUTSTATION', 'Outstation Allowance', 'কর্মস্থলের বাইরে দায়িত্ব ভাতা', 'allowance', '7. Travel, Field & Project', 'fixed', 2500.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, False, False, False, '510708'),
    (138, 'RELOCATION', 'Relocation Allowance', 'স্থানান্তর ভাতা', 'allowance', '7. Travel, Field & Project', 'fixed', 0.0, 0.0, 'basic', False, 'non_taxable_reimbursement', False, False, False, False, False, False, '510709'),
    (139, 'TRANSFER', 'Transfer Allowance', 'বদলি ভাতা', 'allowance', '7. Travel, Field & Project', 'fixed', 0.0, 0.0, 'basic', False, 'non_taxable_reimbursement', False, False, False, False, False, False, '510710'),
    (140, 'MILEAGE', 'Mileage Reimbursement', 'যাতায়াতের দূরত্বভিত্তিক খরচ', 'allowance', '7. Travel, Field & Project', 'fixed', 0.0, 0.0, 'basic', False, 'non_taxable_reimbursement', False, False, False, False, False, False, '510711'),
    (141, 'PARKING', 'Parking Allowance', 'পার্কিং খরচ', 'allowance', '7. Travel, Field & Project', 'fixed', 500.0, 0.0, 'basic', False, 'non_taxable_reimbursement', False, False, False, True, False, False, '510712'),
    (142, 'TOLL', 'Toll Allowance', 'টোল খরচ', 'allowance', '7. Travel, Field & Project', 'fixed', 500.0, 0.0, 'basic', False, 'non_taxable_reimbursement', False, False, False, False, False, False, '510713'),

    # =========================================================================
    # 8. Industry-Specific Allowances (Factory, Garments, Hospital, NGO) (10)
    # =========================================================================
    (145, 'PRODUCTION', 'Production Allowance', 'উৎপাদন ভাতা', 'allowance', '8. Industry-Specific (Factory/NGO)', 'fixed', 1500.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, True, True, False, '510801'),
    (146, 'MACHINE', 'Machine Operation Allowance', 'মেশিন পরিচালনা ভাতা', 'allowance', '8. Industry-Specific (Factory/NGO)', 'fixed', 1000.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, True, True, False, '510802'),
    (147, 'HAZARD', 'Hazard Allowance', 'ঝুঁকিপূর্ণ কাজের ভাতা', 'allowance', '8. Industry-Specific (Factory/NGO)', 'fixed', 2000.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, True, True, False, '510803'),
    (148, 'DUST', 'Dust Allowance', 'ধুলাবালিপূর্ণ পরিবেশে কাজের ভাতা', 'allowance', '8. Industry-Specific (Factory/NGO)', 'fixed', 800.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, True, True, False, '510804'),
    (149, 'HEALTH_RISK', 'Health Risk Allowance', 'স্বাস্থ্যঝুঁকি ভাতা', 'allowance', '8. Industry-Specific (Factory/NGO)', 'fixed', 2000.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, True, True, False, '510805'),
    (150, 'UNIFORM', 'Uniform Allowance', 'পোশাক ভাতা', 'allowance', '8. Industry-Specific (Factory/NGO)', 'fixed', 600.0, 0.0, 'basic', False, 'non_taxable_reimbursement', False, False, False, True, False, False, '510806'),
    (151, 'WASHING', 'Washing Allowance', 'পোশাক পরিষ্কার ভাতা', 'allowance', '8. Industry-Specific (Factory/NGO)', 'fixed', 400.0, 0.0, 'basic', False, 'non_taxable_reimbursement', False, False, False, True, False, False, '510807'),
    (152, 'TOOL', 'Tool Allowance', 'যন্ত্রপাতি ভাতা', 'allowance', '8. Industry-Specific (Factory/NGO)', 'fixed', 500.0, 0.0, 'basic', False, 'non_taxable_reimbursement', False, False, False, True, False, False, '510808'),
    (153, 'REMOTE_AREA', 'Remote Area Allowance', 'প্রত্যন্ত এলাকার ভাতা', 'allowance', '8. Industry-Specific (Factory/NGO)', 'fixed', 3000.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, True, True, False, '510809'),
    (154, 'MEDICAL_RISK', 'Medical Risk Allowance', 'চিকিৎসা ঝুঁকি ভাতা', 'allowance', '8. Industry-Specific (Factory/NGO)', 'fixed', 2500.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, True, True, False, '510810'),

    # =========================================================================
    # 9. Employer-Provided Benefits & Non-cash Perquisites (Separate Category!) (16)
    # =========================================================================
    (260, 'BEN_ACCOMMODATION', 'Company Accommodation (Non-Cash)', 'কোম্পানি প্রদত্ত আবাসন সুবিধা', 'employer_benefit', '9. Employer Non-Cash Perquisites', 'percentage', 0.0, 25.0, 'basic', True, 'perquisite_valuation', False, False, False, True, False, False, '520901'),
    (261, 'BEN_VEHICLE', 'Company Vehicle Facility (Non-Cash)', 'কোম্পানি প্রদত্ত গাড়ি সুবিধা', 'employer_benefit', '9. Employer Non-Cash Perquisites', 'fixed', 10000.0, 0.0, 'basic', True, 'perquisite_valuation', False, False, False, True, False, False, '520902'),
    (262, 'BEN_DRIVER', 'Company Driver Facility (Non-Cash)', 'কোম্পানি প্রদত্ত ড্রাইভার সুবিধা', 'employer_benefit', '9. Employer Non-Cash Perquisites', 'fixed', 5000.0, 0.0, 'basic', True, 'perquisite_valuation', False, False, False, True, False, False, '520903'),
    (263, 'BEN_MOBILE_PHONE', 'Company Mobile Handset', 'কোম্পানি মোবাইল হ্যান্ডসেট সুবিধা', 'employer_benefit', '9. Employer Non-Cash Perquisites', 'fixed', 0.0, 0.0, 'basic', False, 'perquisite_valuation', False, False, False, False, False, False, '520904'),
    (264, 'BEN_COMPANY_SIM', 'Company Official SIM', 'কর্পোরেট সিম সুবিধা', 'employer_benefit', '9. Employer Non-Cash Perquisites', 'fixed', 1000.0, 0.0, 'basic', False, 'perquisite_valuation', False, False, False, True, False, False, '520905'),
    (265, 'BEN_FREE_MEALS', 'Free / Subsidized Meals', 'বিনামূল্যে খাবার সুবিধা', 'employer_benefit', '9. Employer Non-Cash Perquisites', 'fixed', 2000.0, 0.0, 'basic', False, 'perquisite_valuation', False, False, False, True, False, False, '520906'),
    (266, 'BEN_HEALTH_INS', 'Health Insurance Benefit', 'স্বাস্থ্য বীমা সুবিধা', 'employer_benefit', '9. Employer Non-Cash Perquisites', 'fixed', 1500.0, 0.0, 'basic', False, 'perquisite_valuation', False, False, False, True, False, False, '520907'),
    (267, 'BEN_LIFE_INS', 'Life Insurance Benefit', 'জীবন বীমা সুবিধা', 'employer_benefit', '9. Employer Non-Cash Perquisites', 'fixed', 1000.0, 0.0, 'basic', False, 'perquisite_valuation', False, False, False, True, False, False, '520908'),
    (268, 'BEN_GROUP_INS', 'Group Insurance Coverage', 'গ্রুপ বীমা সুবিধা', 'employer_benefit', '9. Employer Non-Cash Perquisites', 'fixed', 500.0, 0.0, 'basic', False, 'perquisite_valuation', False, False, False, True, False, False, '520909'),
    (269, 'BEN_CHILD_EDU', 'Child Education Support Benefit', 'সন্তানের শিক্ষা সহায়তা সুবিধা', 'employer_benefit', '9. Employer Non-Cash Perquisites', 'fixed', 2000.0, 0.0, 'basic', True, 'perquisite_valuation', False, False, False, True, False, False, '520910'),
    (270, 'BEN_DAYCARE', 'Daycare / Creche Facility', 'ডে-কেয়ার সুবিধা', 'employer_benefit', '9. Employer Non-Cash Perquisites', 'fixed', 1500.0, 0.0, 'basic', False, 'perquisite_valuation', False, False, False, True, False, False, '520911'),
    (271, 'BEN_STAFF_WELFARE', 'Staff Welfare Benefits', 'কর্মী কল্যাণ সুবিধা', 'employer_benefit', '9. Employer Non-Cash Perquisites', 'fixed', 500.0, 0.0, 'basic', False, 'perquisite_valuation', False, False, False, True, False, False, '520912'),
    (272, 'BEN_PF_RECOGNIZED', 'Employer PF Benefit Right', 'প্রভিডেন্ট ফান্ড সুবিধা', 'employer_benefit', '9. Employer Non-Cash Perquisites', 'fixed', 0.0, 0.0, 'basic', False, 'employer_non_salary', False, False, False, True, False, False, '520913'),
    (273, 'BEN_GRATUITY', 'Gratuity Benefit Right', 'গ্র্যাচুইটি সুবিধা', 'employer_benefit', '9. Employer Non-Cash Perquisites', 'fixed', 0.0, 0.0, 'basic', False, 'employer_non_salary', False, False, False, True, False, False, '520914'),
    (274, 'BEN_RETIREMENT', 'Retirement Benefit', 'অবসরকালীন সুবিধা', 'employer_benefit', '9. Employer Non-Cash Perquisites', 'fixed', 0.0, 0.0, 'basic', False, 'employer_non_salary', False, False, False, True, False, False, '520915'),
    (275, 'BEN_SHARE_ESOP', 'Employee Share / ESOP Benefits', 'কর্মী শেয়ার সুবিধা', 'employer_benefit', '9. Employer Non-Cash Perquisites', 'fixed', 0.0, 0.0, 'basic', True, 'perquisite_valuation', False, False, False, False, False, False, '520916'),

    # =========================================================================
    # 10. Employee Salary Deductions (22 — Statutory Compliance & Approval Flags!)
    # =========================================================================
    (160, 'PF_EMPLOYEE', 'Employee Provident Fund', 'কর্মীর প্রভিডেন্ট ফান্ড', 'deduction', '10. Employee Salary Deductions', 'percentage', 0.0, 10.0, 'basic', False, 'employer_non_salary', True, False, False, True, False, False, '210401'),
    (162, 'INCOME_TAX', 'Income Tax / TDS', 'আয়কর কর্তন (TDS)', 'deduction', '10. Employee Salary Deductions', 'fixed', 0.0, 0.0, 'basic', False, 'employer_non_salary', False, False, False, True, False, False, '210402'),
    (164, 'LOAN', 'Employee Loan Recovery', 'কর্মী ঋণ আদায়', 'deduction', '10. Employee Salary Deductions', 'fixed', 0.0, 0.0, 'basic', False, 'employer_non_salary', False, False, False, True, False, False, '120501'),
    (165, 'SALARY_ADVANCE', 'Salary Advance Recovery', 'অগ্রিম বেতন সমন্বয়', 'deduction', '10. Employee Salary Deductions', 'fixed', 0.0, 0.0, 'basic', False, 'employer_non_salary', False, False, False, False, False, False, '120502'),
    (166, 'OVERPAYMENT', 'Excess Salary Recovery', 'অতিরিক্ত বেতন সমন্বয়', 'deduction', '10. Employee Salary Deductions', 'fixed', 0.0, 0.0, 'basic', False, 'employer_non_salary', False, False, False, False, False, True, '120503'),
    (168, 'ABSENCE', 'Unauthorized Absence Deduction', 'অননুমোদিত অনুপস্থিতির কর্তন', 'deduction', '10. Employee Salary Deductions', 'attendance_based', 0.0, 0.0, 'gross', False, 'employer_non_salary', False, False, False, False, False, False, '510901'),
    (170, 'LATE_ADJUSTMENT', 'Late Attendance Adjustment', 'বিলম্বজনিত বেতন সমন্বয়', 'deduction', '10. Employee Salary Deductions', 'attendance_based', 0.0, 0.0, 'basic', False, 'employer_non_salary', False, False, False, False, False, True, '510902'),
    (172, 'UNPAID_LEAVE', 'Unpaid Leave Deduction (LWP)', 'বিনা বেতনের ছুটির কর্তন', 'deduction', '10. Employee Salary Deductions', 'attendance_based', 0.0, 0.0, 'gross', False, 'employer_non_salary', False, False, False, False, False, False, '510903'),
    (174, 'HOUSE_RENT_RECOVERY', 'Accommodation Recovery', 'বাসস্থান খরচ আদায়', 'deduction', '10. Employee Salary Deductions', 'fixed', 1500.0, 0.0, 'basic', False, 'employer_non_salary', False, False, False, True, False, False, '420101'),
    (175, 'UTILITY_RECOVERY', 'Utility Bill Recovery', 'ইউটিলিটি বিল আদায়', 'deduction', '10. Employee Salary Deductions', 'fixed', 500.0, 0.0, 'basic', False, 'employer_non_salary', False, False, False, True, False, False, '420102'),
    (176, 'FOOD_RECOVERY', 'Food / Meal Recovery', 'খাবারের খরচ আদায়', 'deduction', '10. Employee Salary Deductions', 'fixed', 800.0, 0.0, 'basic', False, 'employer_non_salary', False, False, False, True, False, False, '420103'),
    (177, 'TRANSPORT_RECOVERY', 'Transport Recovery', 'পরিবহন খরচ আদায়', 'deduction', '10. Employee Salary Deductions', 'fixed', 1000.0, 0.0, 'basic', False, 'employer_non_salary', False, False, False, True, False, False, '420104'),
    (178, 'INSURANCE_EMPLOYEE', 'Employee Insurance Contribution', 'কর্মীর বীমা চাঁদা', 'deduction', '10. Employee Salary Deductions', 'fixed', 350.0, 0.0, 'basic', False, 'employer_non_salary', False, False, False, True, False, False, '210405'),
    (179, 'WELFARE_FUND', 'Welfare Fund Contribution', 'কল্যাণ তহবিল চাঁদা', 'deduction', '10. Employee Salary Deductions', 'fixed', 200.0, 0.0, 'basic', False, 'employer_non_salary', False, False, False, True, False, False, '210406'),
    (180, 'COOPERATIVE', 'Cooperative Society Contribution', 'সমবায় সমিতির চাঁদা', 'deduction', '10. Employee Salary Deductions', 'fixed', 500.0, 0.0, 'basic', False, 'employer_non_salary', False, False, False, True, False, False, '210407'),
    (181, 'SECURITY_DEP', 'Security Deposit Retention', 'জামানত কর্তন', 'deduction', '10. Employee Salary Deductions', 'fixed', 1000.0, 0.0, 'basic', False, 'employer_non_salary', False, False, False, True, False, True, '210408'),
    (182, 'UNION_CLUB_FEE', 'Club / Association / Union Fee', 'ক্লাব ও ইউনিয়ন চাঁদা', 'deduction', '10. Employee Salary Deductions', 'fixed', 150.0, 0.0, 'basic', False, 'employer_non_salary', False, False, False, True, False, False, '210409'),
    (183, 'MOBILE_EXC', 'Excess Mobile / Fuel Bill Recovery', 'অতিরিক্ত মোবাইল ও জ্বালানি বিল কর্তন', 'deduction', '10. Employee Salary Deductions', 'fixed', 0.0, 0.0, 'basic', False, 'employer_non_salary', False, False, False, False, False, True, '420105'),
    (184, 'COURT_ORDER', 'Court-Ordered Deduction', 'আদালতের নির্দেশে কর্তন', 'deduction', '10. Employee Salary Deductions', 'fixed', 0.0, 0.0, 'basic', False, 'employer_non_salary', False, False, False, False, False, True, '210410'),
    (185, 'DAMAGE_RECOVERY', 'Damage / Loss Recovery (BD Labour Act Sec 125)', 'ক্ষয়ক্ষতি বা লোকসান আদায়', 'deduction', '10. Employee Salary Deductions', 'fixed', 0.0, 0.0, 'basic', False, 'employer_non_salary', False, False, False, False, False, True, '420106'),
    (186, 'OTHER_DEDUCTION', 'Other Authorized Deduction', 'অন্যান্য অনুমোদিত কর্তন', 'deduction', '10. Employee Salary Deductions', 'fixed', 0.0, 0.0, 'basic', False, 'employer_non_salary', False, False, False, False, False, True, '210411'),
    (195, 'STAMP', 'Revenue Stamp (BD Stamp Act ৳10)', 'রেভিনিউ স্ট্যাম্প (১০ টাকা)', 'deduction', '10. Employee Salary Deductions', 'fixed', 10.0, 0.0, 'basic', False, 'employer_non_salary', False, False, False, True, False, False, '210412'),

    # =========================================================================
    # 11. Employer Contributions & Provisions (Separate Category — NOT Deducted!) (8)
    # =========================================================================
    (210, 'PF_EMPLOYER', 'Employer Provident Fund Contribution', 'নিয়োগকর্তার প্রভিডেন্ট ফান্ড অবদান', 'employer_contribution', '11. Employer Contributions & Provisions', 'percentage', 0.0, 10.0, 'basic', False, 'employer_non_salary', True, False, False, True, False, False, '520101'),
    (212, 'GRATUITY', 'Gratuity Provision', 'গ্র্যাচুইটি প্রভিশন', 'employer_contribution', '11. Employer Contributions & Provisions', 'percentage', 0.0, 8.33, 'basic', False, 'employer_non_salary', False, False, False, True, False, False, '520102'),
    (214, 'INSURANCE_EMPLOYER', 'Employer Insurance Contribution', 'নিয়োগকর্তার বীমা অবদান', 'employer_contribution', '11. Employer Contributions & Provisions', 'fixed', 500.0, 0.0, 'basic', False, 'employer_non_salary', False, False, False, True, False, False, '520103'),
    (216, 'WELFARE_EMPLOYER', 'Employer Welfare Contribution', 'নিয়োগকর্তার কল্যাণ তহবিল অবদান', 'employer_contribution', '11. Employer Contributions & Provisions', 'fixed', 250.0, 0.0, 'basic', False, 'employer_non_salary', False, False, False, True, False, False, '520104'),
    (218, 'BONUS_PROVISION', 'Festival Bonus Provision', 'উৎসব বোনাস প্রভিশন', 'employer_contribution', '11. Employer Contributions & Provisions', 'percentage', 0.0, 16.67, 'basic', False, 'employer_non_salary', False, False, False, True, False, False, '520105'),
    (220, 'LEAVE_PROVISION', 'Leave Encashment Provision', 'ছুটি নগদায়ন প্রভিশন', 'employer_contribution', '11. Employer Contributions & Provisions', 'percentage', 0.0, 5.0, 'basic', False, 'employer_non_salary', False, False, False, True, False, False, '520106'),
    (222, 'SEVERANCE_PROVISION', 'Separation Benefit Provision', 'চূড়ান্ত নিষ্পত্তি প্রভিশন', 'employer_contribution', '11. Employer Contributions & Provisions', 'percentage', 0.0, 4.0, 'basic', False, 'employer_non_salary', False, False, False, True, False, False, '520107'),
    (224, 'PENSION_EMPLOYER', 'Employer Pension Contribution', 'নিয়োগকর্তার পেনশন অবদান', 'employer_contribution', '11. Employer Contributions & Provisions', 'percentage', 0.0, 5.0, 'basic', False, 'employer_non_salary', False, False, False, True, False, False, '520108'),

    # =========================================================================
    # 12. Payroll Run Variable Payments (Non-Recurring Monthly Run Items) (9)
    # =========================================================================
    (196, 'OT_AMOUNT', 'Overtime Payment (Run Variable)', 'ওভারটাইম পেমেন্ট', 'overtime_variable', '12. Payroll Run Variable Payments', 'fixed', 0.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, False, False, False, '510520'),
    (197, 'ATTENDANCE_INCENTIVE', 'Attendance Incentive (Run Variable)', 'হাজিরা প্রণোদনা', 'bonus_incentive', '12. Payroll Run Variable Payments', 'fixed', 0.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, False, False, False, '510420'),
    (198, 'SALES_INCENTIVE', 'Sales Incentive (Run Variable)', 'বিক্রয় প্রণোদনা', 'bonus_incentive', '12. Payroll Run Variable Payments', 'fixed', 0.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, False, False, False, '510421'),
    (199, 'COMMISSION', 'Commission (Run Variable)', 'কমিশন', 'bonus_incentive', '12. Payroll Run Variable Payments', 'fixed', 0.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, False, False, False, '510422'),
    (200, 'BONUS_AMOUNT', 'Bonus Payment (Run Variable)', 'বোনাস পেমেন্ট', 'bonus_incentive', '12. Payroll Run Variable Payments', 'fixed', 0.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, False, False, False, '510320'),
    (201, 'ARREAR_AMOUNT', 'Arrear Adjustment Payment', 'বকেয়া সমন্বয় পেমেন্ট', 'bonus_incentive', '12. Payroll Run Variable Payments', 'fixed', 0.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, False, False, False, '510321'),
    (202, 'LEAVE_ENCASH_AMOUNT', 'Leave Encashment Payment', 'ছুটি নগদায়ন অর্থ', 'bonus_incentive', '12. Payroll Run Variable Payments', 'fixed', 0.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, False, False, False, '510322'),
    (203, 'REIMBURSEMENT', 'Official Expense Reimbursement', 'অফিশিয়াল ব্যয় পুনর্ভরণ', 'overtime_variable', '12. Payroll Run Variable Payments', 'fixed', 0.0, 0.0, 'basic', False, 'non_taxable_reimbursement', False, False, False, False, False, False, '510720'),
    (204, 'FINAL_SETTLEMENT', 'Final Settlement Payment', 'চূড়ান্ত নিষ্পত্তি অর্থ', 'overtime_variable', '12. Payroll Run Variable Payments', 'fixed', 0.0, 0.0, 'basic', True, 'fully_taxable', False, False, False, False, False, False, '510920'),
]


class DslSalaryHeadSeeder(models.Model):
    _inherit = 'dsl.salary.head'

    @api.model
    def _seed_bd_salary_components(self):
        """Idempotently upgrades legacy codes & seeds all 155 Bangladesh Allowances, Deductions, Benefits & Employer Contributions."""
        self.env.cr.execute(
            "UPDATE ir_model_data SET noupdate = TRUE WHERE module = 'DSL_HRMS_salary_structure' AND model = 'dsl.salary.head'"
        )
        Head = self.sudo().with_context(active_test=False)

        # 1. Cleanly migrate any earlier short codes to canonical Bangladesh standard codes
        for old_code, new_code in LEGACY_CODE_RENAME_MAP.items():
            old_rec = Head.search([('code', '=', old_code), ('company_id', '=', False)], limit=1)
            new_rec = Head.search([('code', '=', new_code), ('company_id', '=', False)], limit=1)
            if old_rec and not new_rec:
                old_rec.write({'code': new_code})

        existing_map = {
            h.code: h for h in Head.search([('company_id', '=', False)])
        }

        to_create = []
        for row in BD_COMPLETE_SALARY_CATALOG:
            (
                seq, code, name, name_bn, cat, sub_grp, ctype, amt, pct,
                based_on, taxable, tax_treat, pf, ot, bonus, recur, pro, app_req, acc
            ) = row
            vals = {
                'sequence': seq,
                'code': code,
                'name': name,
                'name_bn': name_bn,
                'category': cat,
                'sub_group': sub_grp,
                'calculation_type': ctype,
                'amount': amt,
                'percentage': pct,
                'based_on': based_on,
                'default_calc_type': ('pct_gross' if based_on == 'gross' else 'pct_basic') if ctype == 'percentage' else 'fixed',
                'default_value': pct if ctype == 'percentage' else amt,
                'is_taxable': taxable,
                'tax_treatment': tax_treat,
                'is_pf_applicable': pf,
                'is_ot_applicable': ot,
                'is_bonus_applicable': bonus,
                'is_recurring': recur,
                'is_prorated': pro,
                'approval_required': app_req,
                'account_code': acc,
                'debit_account_code': acc if cat != 'deduction' else '210300',
                'credit_account_code': '210300' if cat not in ('deduction', 'employer_contribution') else acc,
            }
            if code in existing_map:
                rec = existing_map[code]
                rec.write({
                    'category': cat,
                    'sub_group': sub_grp,
                    'name_bn': rec.name_bn or name_bn,
                    'tax_treatment': tax_treat,
                    'approval_required': app_req,
                    'is_pf_applicable': pf,
                    'is_ot_applicable': ot,
                    'is_bonus_applicable': bonus,
                    'is_recurring': recur,
                    'account_code': rec.account_code or acc,
                    'debit_account_code': rec.debit_account_code or vals['debit_account_code'],
                    'credit_account_code': rec.credit_account_code or vals['credit_account_code'],
                })
            else:
                to_create.append(vals)

        if to_create:
            Head.create(to_create)

        # 2. Seed Default Configurable Structure Rules onto Templates if empty
        all_heads = {h.code: h for h in Head.search([('company_id', '=', False)])}
        Rule = self.env['dsl.salary.structure.rule'].sudo()

        corp = self.env.ref('DSL_HRMS_salary_structure.structure_bd_corporate_std', raise_if_not_found=False)
        if corp and not corp.rule_ids:
            corp_rules = [
                (10, 'BASIC', 'percentage', 0.0, 50.0, 'gross', ''),
                (20, 'HRA', 'percentage', 0.0, 25.0, 'gross', ''),
                (30, 'MEDICAL', 'percentage', 0.0, 10.0, 'gross', ''),
                (40, 'CONVEYANCE', 'percentage', 0.0, 10.0, 'gross', ''),
                (50, 'SPECIAL', 'percentage', 0.0, 5.0, 'gross', ''),
                (52, 'MOBILE', 'fixed', 1000.0, 0.0, 'basic', ''),
                (160, 'PF_EMPLOYEE', 'percentage', 0.0, 10.0, 'basic', ''),
                (195, 'STAMP', 'fixed', 10.0, 0.0, 'basic', ''),
                (210, 'PF_EMPLOYER', 'percentage', 0.0, 10.0, 'basic', ''),
                (212, 'GRATUITY', 'percentage', 0.0, 8.33, 'basic', ''),
            ]
            for seq, cd, ct, am, pc, bo, fm in corp_rules:
                if cd in all_heads:
                    Rule.create({
                        'structure_id': corp.id,
                        'sequence': seq,
                        'head_id': all_heads[cd].id,
                        'calculation_type': ct,
                        'amount': am,
                        'percentage': pc,
                        'based_on': bo,
                        'formula': fm,
                    })

        rmg = self.env.ref('DSL_HRMS_salary_structure.structure_bd_rmg_factory', raise_if_not_found=False)
        if rmg and not rmg.rule_ids:
            rmg_rules = [
                (10, 'BASIC', 'formula', 0.0, 0.0, 'gross', '(GROSS - 2450) / 1.5'),
                (20, 'HRA', 'percentage', 0.0, 50.0, 'basic', ''),
                (30, 'MEDICAL', 'fixed', 750.0, 0.0, 'basic', ''),
                (40, 'CONVEYANCE', 'fixed', 450.0, 0.0, 'basic', ''),
                (50, 'FOOD', 'fixed', 1250.0, 0.0, 'basic', ''),
                (86, 'ATTENDANCE_BONUS', 'fixed', 750.0, 0.0, 'basic', ''),
                (195, 'STAMP', 'fixed', 10.0, 0.0, 'basic', ''),
            ]
            for seq, cd, ct, am, pc, bo, fm in rmg_rules:
                if cd in all_heads:
                    Rule.create({
                        'structure_id': rmg.id,
                        'sequence': seq,
                        'head_id': all_heads[cd].id,
                        'calculation_type': ct,
                        'amount': am,
                        'percentage': pc,
                        'based_on': bo,
                        'formula': fm,
                    })

        ngo = self.env.ref('DSL_HRMS_salary_structure.structure_bd_ngo_project', raise_if_not_found=False)
        if ngo and not ngo.rule_ids:
            ngo_rules = [
                (10, 'BASIC', 'percentage', 0.0, 60.0, 'gross', ''),
                (20, 'HRA', 'percentage', 0.0, 30.0, 'gross', ''),
                (30, 'MEDICAL', 'percentage', 0.0, 10.0, 'gross', ''),
                (133, 'FA', 'fixed', 2500.0, 0.0, 'basic', ''),
                (160, 'PF_EMPLOYEE', 'percentage', 0.0, 10.0, 'basic', ''),
                (210, 'PF_EMPLOYER', 'percentage', 0.0, 10.0, 'basic', ''),
                (212, 'GRATUITY', 'percentage', 0.0, 8.33, 'basic', ''),
                (214, 'INSURANCE_EMPLOYER', 'fixed', 500.0, 0.0, 'basic', ''),
            ]
            for seq, cd, ct, am, pc, bo, fm in ngo_rules:
                if cd in all_heads:
                    Rule.create({
                        'structure_id': ngo.id,
                        'sequence': seq,
                        'head_id': all_heads[cd].id,
                        'calculation_type': ct,
                        'amount': am,
                        'percentage': pc,
                        'based_on': bo,
                        'formula': fm,
                    })

