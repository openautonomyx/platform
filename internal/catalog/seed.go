package catalog

import "github.com/openautonomyx/platform/internal/engine"

func fptr(v float64) *float64 { return &v }

// Seed registers MetaKube's built-in decision services. It panics if a seed
// model is invalid, since that is a programming error.
func Seed(c *Catalog) {
	for _, m := range SeedModels() {
		if _, err := c.Put(m); err != nil {
			panic("catalog: invalid seed model " + m.ID + ": " + err.Error())
		}
	}
}

// SeedModels returns the built-in decision models.
func SeedModels() []*engine.Model {
	return []*engine.Model{loanApprovalModel(), fraudCheckModel()}
}

// loanApprovalModel is the canonical decision-intelligence example: a consumer
// loan-approval decision service combining knockout rules, a risk scorecard and
// a decision table.
func loanApprovalModel() *engine.Model {
	return &engine.Model{
		ID:          "loan-approval",
		Name:        "Loan Approval Decision Service",
		Version:     "1.4.0",
		Description: "Adjudicates consumer loan applications into APPROVE, REVIEW or DECLINE using affordability rules, a transparent risk scorecard and a decision table.",
		Tags:        []string{"lending", "credit-risk", "underwriting"},
		Inputs: []engine.InputField{
			{Key: "creditScore", Label: "Credit Score", Type: "number", Required: true, Min: fptr(300), Max: fptr(850), Example: 712},
			{Key: "annualIncome", Label: "Annual Income (USD)", Type: "number", Required: true, Min: fptr(0), Example: 84000},
			{Key: "monthlyDebt", Label: "Monthly Debt Payments (USD)", Type: "number", Required: true, Min: fptr(0), Example: 1450},
			{Key: "loanAmount", Label: "Requested Loan Amount (USD)", Type: "number", Required: true, Min: fptr(0), Example: 24000},
			{Key: "employmentYears", Label: "Years in Current Employment", Type: "number", Required: true, Min: fptr(0), Example: 4},
			{Key: "age", Label: "Applicant Age", Type: "number", Required: true, Min: fptr(0), Example: 36},
			{Key: "loanPurpose", Label: "Loan Purpose", Type: "string", Required: false, Enum: []string{"auto", "home", "personal", "education", "business"}, Example: "auto"},
			{Key: "priorDefaults", Label: "Number of Prior Defaults", Type: "number", Required: false, Min: fptr(0), Example: 0},
		},
		Derivations: []engine.Derivation{
			{Key: "monthlyIncome", Label: "Monthly Income", Expr: "annualIncome / 12"},
			{Key: "dti", Label: "Debt-to-Income Ratio", Expr: "monthlyDebt / max(monthlyIncome, 1)"},
			{Key: "loanToIncome", Label: "Loan-to-Income Ratio", Expr: "loanAmount / max(annualIncome, 1)"},
		},
		Knockouts: []engine.Rule{
			{ID: "ko_age", Code: "KO_AGE", When: "age < 18", Reason: "Applicant below minimum age of 18"},
			{ID: "ko_credit_floor", Code: "KO_SCORE", When: "creditScore < 520", Reason: "Credit score below minimum threshold of 520"},
			{ID: "ko_dti", Code: "KO_DTI", When: "dti > 0.55", Reason: "Debt-to-income ratio exceeds 55%"},
			{ID: "ko_income", Code: "KO_INCOME", When: "annualIncome < 15000", Reason: "Annual income below minimum of $15,000"},
			{ID: "ko_defaults", Code: "KO_DEFAULTS", When: "priorDefaults >= 3", Reason: "Three or more prior defaults on record"},
		},
		Scorecard: &engine.Scorecard{
			Base: 45, Min: 0, Max: 100, Output: "riskScore",
			Factors: []engine.ScoreFactor{
				{ID: "credit_excellent", When: "creditScore >= 760", Points: 28, Reason: "Excellent credit score (>=760)"},
				{ID: "credit_very_good", When: "creditScore >= 700 && creditScore < 760", Points: 20, Reason: "Very good credit score (700-759)"},
				{ID: "credit_good", When: "creditScore >= 640 && creditScore < 700", Points: 10, Reason: "Good credit score (640-699)"},
				{ID: "credit_fair", When: "creditScore >= 580 && creditScore < 640", Points: -5, Reason: "Fair credit score (580-639)"},
				{ID: "dti_low", When: "dti <= 0.20", Points: 18, Reason: "Low debt-to-income (<=20%)"},
				{ID: "dti_moderate", When: "dti > 0.20 && dti <= 0.35", Points: 6, Reason: "Moderate debt-to-income (20-35%)"},
				{ID: "dti_high", When: "dti > 0.45", Points: -15, Reason: "High debt-to-income (>45%)"},
				{ID: "tenure_strong", When: "employmentYears >= 5", Points: 8, Reason: "Stable employment (5+ years)"},
				{ID: "tenure_short", When: "employmentYears < 1", Points: -8, Reason: "Short employment tenure (<1 year)"},
				{ID: "lti_high", When: "loanToIncome > 0.5", Points: -10, Reason: "Loan amount high relative to income"},
				{ID: "clean_history", When: "priorDefaults == 0", Points: 6, Reason: "No prior defaults"},
			},
		},
		Decision: &engine.DecisionTable{
			HitPolicy: "FIRST",
			Rules: []engine.DecisionRow{
				{ID: "tier_a", When: "riskScore >= 78", Decision: "APPROVE", Tier: "A", Reason: "Strong risk profile", Set: map[string]any{"recommendedApr": 6.9}},
				{ID: "tier_b", When: "riskScore >= 65", Decision: "APPROVE", Tier: "B", Reason: "Acceptable risk profile", Set: map[string]any{"recommendedApr": 10.4}},
				{ID: "tier_c", When: "riskScore >= 50", Decision: "REVIEW", Tier: "C", Reason: "Borderline risk profile requires manual review"},
				{ID: "tier_d", When: "true", Decision: "DECLINE", Tier: "D", Reason: "Risk score below approval threshold"},
			},
		},
		Outputs: []engine.OutputField{
			{Key: "decision", Label: "Decision"},
			{Key: "riskScore", Label: "Risk Score"},
			{Key: "tier", Label: "Risk Tier"},
			{Key: "recommendedApr", Label: "Recommended APR"},
		},
	}
}

// fraudCheckModel is a lightweight real-time transaction fraud screen, included
// to demonstrate composing multiple decision services in one platform.
func fraudCheckModel() *engine.Model {
	return &engine.Model{
		ID:          "fraud-check",
		Name:        "Transaction Fraud Screen",
		Version:     "0.9.0",
		Description: "Scores a payment transaction for fraud risk and routes high-risk transactions to review or decline.",
		Tags:        []string{"payments", "fraud", "real-time"},
		Inputs: []engine.InputField{
			{Key: "amount", Label: "Transaction Amount (USD)", Type: "number", Required: true, Min: fptr(0), Example: 240},
			{Key: "accountAgeDays", Label: "Account Age (days)", Type: "number", Required: true, Min: fptr(0), Example: 420},
			{Key: "countryMismatch", Label: "Billing/IP Country Mismatch", Type: "boolean", Required: true, Example: false},
			{Key: "velocity1h", Label: "Transactions in Last Hour", Type: "number", Required: true, Min: fptr(0), Example: 2},
			{Key: "isNewDevice", Label: "New Device", Type: "boolean", Required: true, Example: false},
		},
		Knockouts: []engine.Rule{
			{ID: "ko_velocity", Code: "KO_VELOCITY", When: "velocity1h >= 12", Reason: "Transaction velocity exceeds safe threshold"},
		},
		Scorecard: &engine.Scorecard{
			Base: 80, Min: 0, Max: 100, Output: "riskScore",
			Factors: []engine.ScoreFactor{
				{ID: "geo_mismatch", When: "countryMismatch == true", Points: -35, Reason: "Billing and IP country mismatch"},
				{ID: "new_account", When: "accountAgeDays < 30", Points: -20, Reason: "Account is less than 30 days old"},
				{ID: "high_amount", When: "amount > 1000", Points: -15, Reason: "High transaction amount"},
				{ID: "new_device", When: "isNewDevice == true", Points: -12, Reason: "Transaction from a new device"},
				{ID: "velocity", When: "velocity1h >= 5", Points: -18, Reason: "Elevated transaction velocity"},
			},
		},
		Decision: &engine.DecisionTable{
			HitPolicy: "FIRST",
			Rules: []engine.DecisionRow{
				{ID: "clear", When: "riskScore >= 70", Decision: "APPROVE", Tier: "LOW", Reason: "Low fraud risk"},
				{ID: "review", When: "riskScore >= 45", Decision: "REVIEW", Tier: "MEDIUM", Reason: "Medium fraud risk, manual review"},
				{ID: "block", When: "true", Decision: "DECLINE", Tier: "HIGH", Reason: "High fraud risk"},
			},
		},
		Outputs: []engine.OutputField{
			{Key: "decision", Label: "Decision"},
			{Key: "riskScore", Label: "Fraud Safety Score"},
		},
	}
}
