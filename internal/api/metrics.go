package api

import (
	"sort"
	"time"

	"github.com/openautonomyx/platform/internal/store"
)

type scoreBucket struct {
	Range string `json:"range"`
	Count int    `json:"count"`
}

type reasonCount struct {
	Code  string `json:"code"`
	Count int    `json:"count"`
}

type throughput struct {
	LastMinute int `json:"lastMinute"`
	Last5Min   int `json:"last5Minutes"`
	LastHour   int `json:"lastHour"`
}

// metrics is the aggregated monitoring view over recorded decision runs.
type metrics struct {
	Total          int            `json:"total"`
	ByDecision     map[string]int `json:"byDecision"`
	ByModel        map[string]int `json:"byModel"`
	ApprovalRate   float64        `json:"approvalRate"`
	ReviewRate     float64        `json:"reviewRate"`
	DeclineRate    float64        `json:"declineRate"`
	AvgRiskScore   float64        `json:"avgRiskScore"`
	AvgConfidence  float64        `json:"avgConfidence"`
	ScoreHistogram []scoreBucket  `json:"scoreHistogram"`
	TopReasonCodes []reasonCount  `json:"topReasonCodes"`
	PendingReviews int            `json:"pendingReviews"`
	Resolved       int            `json:"resolvedReviews"`
	Overrides      int            `json:"reviewOverrides"`
	OverrideRate   float64        `json:"overrideRate"`
	Throughput     throughput     `json:"throughput"`
	GeneratedAt    time.Time      `json:"generatedAt"`
}

func computeMetrics(runs []*store.Run, now time.Time) metrics {
	m := metrics{
		ByDecision:  map[string]int{"APPROVE": 0, "REVIEW": 0, "DECLINE": 0},
		ByModel:     map[string]int{},
		GeneratedAt: now,
	}
	buckets := make([]int, 10) // 0-9,10-19,...,90-100
	reasons := map[string]int{}
	var sumScore, sumConf float64

	for _, run := range runs {
		m.Total++
		m.ByDecision[run.Outcome.Decision]++
		m.ByModel[run.ModelID]++
		sumScore += run.Outcome.RiskScore
		sumConf += run.Outcome.Confidence

		idx := int(run.Outcome.RiskScore) / 10
		if idx < 0 {
			idx = 0
		}
		if idx > 9 {
			idx = 9
		}
		buckets[idx]++

		for _, rc := range run.Outcome.ReasonCodes {
			reasons[rc.Code]++
		}

		switch run.Status {
		case store.StatusPendingReview:
			m.PendingReviews++
		case store.StatusResolved:
			m.Resolved++
			if run.Review != nil && run.Review.Overridden {
				m.Overrides++
			}
		}

		switch {
		case run.CreatedAt.After(now.Add(-time.Minute)):
			m.Throughput.LastMinute++
			m.Throughput.Last5Min++
			m.Throughput.LastHour++
		case run.CreatedAt.After(now.Add(-5 * time.Minute)):
			m.Throughput.Last5Min++
			m.Throughput.LastHour++
		case run.CreatedAt.After(now.Add(-time.Hour)):
			m.Throughput.LastHour++
		}
	}

	if m.Total > 0 {
		m.ApprovalRate = round3(float64(m.ByDecision["APPROVE"]) / float64(m.Total))
		m.ReviewRate = round3(float64(m.ByDecision["REVIEW"]) / float64(m.Total))
		m.DeclineRate = round3(float64(m.ByDecision["DECLINE"]) / float64(m.Total))
		m.AvgRiskScore = round1(sumScore / float64(m.Total))
		m.AvgConfidence = round3(sumConf / float64(m.Total))
	}
	if m.Resolved > 0 {
		m.OverrideRate = round3(float64(m.Overrides) / float64(m.Resolved))
	}

	for i, c := range buckets {
		lo := i * 10
		hi := lo + 9
		if i == 9 {
			hi = 100
		}
		m.ScoreHistogram = append(m.ScoreHistogram, scoreBucket{Range: itoaRange(lo, hi), Count: c})
	}

	m.TopReasonCodes = topReasons(reasons, 10)
	return m
}

func topReasons(reasons map[string]int, n int) []reasonCount {
	out := make([]reasonCount, 0, len(reasons))
	for code, c := range reasons {
		out = append(out, reasonCount{Code: code, Count: c})
	}
	sort.Slice(out, func(i, j int) bool {
		if out[i].Count != out[j].Count {
			return out[i].Count > out[j].Count
		}
		return out[i].Code < out[j].Code
	})
	if len(out) > n {
		out = out[:n]
	}
	return out
}

func itoaRange(lo, hi int) string {
	return itoa(lo) + "-" + itoa(hi)
}

func itoa(n int) string {
	if n == 0 {
		return "0"
	}
	var buf [12]byte
	i := len(buf)
	for n > 0 {
		i--
		buf[i] = byte('0' + n%10)
		n /= 10
	}
	return string(buf[i:])
}

func round1(f float64) float64 { return float64(int64(f*10+0.5)) / 10 }
func round3(f float64) float64 { return float64(int64(f*1000+0.5)) / 1000 }
