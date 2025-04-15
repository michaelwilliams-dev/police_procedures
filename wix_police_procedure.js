$w.onReady(() => {
  console.log("✅ Police Procedures: Form loaded");

  $w('#submitQueryButton').onClick(submitQueryButton_click);

  $w('#inputDiscipline').value = "Police Procedures";
  $w('#inputSourceContext').value = "This response is based on UK police internal procedures, compliance policies, and welfare guidance.";
  $w('#inputJobCode').value = 1011;

  $w('#dropdownJobTitle').options = [
    { label: "Support & Technical Staff —", value: "", disabled: false },
    { label: "Control Room Operator", value: "Control Room Operator" },
    { label: "Scenes of Crime Officer", value: "Scenes of Crime Officer" },
    { label: "Forensic", value: "Forensic" },
    { label: "Digital Evidence Officer", value: "Digital Evidence Officer" },
    { label: "Body Worn Camera Admin", value: "Body Worn Camera Admin" },
    { label: "Evidence Handler", value: "Evidence Handler" },
    { label: "Internal Auditor", value: "Internal Auditor" },
    { label: "HR", value: "HR" },
    { label: "Welfare", value: "Welfare" },
    { label: "IT & Systems Support", value: "IT & Systems Support" },
    { label: "Other", value: "Other" }
  ];

  $w('#dropdownTimeline').options = [
  { label: "— Please select a timeline —", value: "", disabled: false },  // 👈 new placeholder
  { label: "Shift Today", value: "Shift Today" },
  { label: "Next 48 Hours", value: "Next 48 Hours" },
  { label: "Next Rota Cycle", value: "Next Rota Cycle" },
  { label: "Following Review", value: "Following Review" },
  { label: "Pending Inspection", value: "Pending Inspection" },
  { label: "Historical Review", value: "Historical Review" },
  { label: "Other", value: "Other" }
];

  $w('#dropdownSiteName').options = [
    { label: "HQ Records", value: "HQ Records" },
    { label: "IT Department", value: "IT Department" },
    { label: "Custody Centre", value: "Custody Centre" },
    { label: "Admin Block", value: "Admin Block" },
    { label: "Internal Audit", value: "Internal Audit" },
    { label: "Training Wing", value: "Training Wing" },
    { label: "Other", value: "Other" }
  ];

  $w('#dropdownSearchType').options = [
    { label: "HR Complaint", value: "HR Complaint" },
    { label: "Data Breach", value: "Data Breach" },
    { label: "Staff Misconduct", value: "Staff Misconduct" },
    { label: "PPE Audit", value: "PPE Audit" },
    { label: "IT Security", value: "IT Security" },
    { label: "Policy Breach", value: "Policy Breach" },
    { label: "Other", value: "Other" }
  ];

  $w('#dropdownFunnel1').options = [
    { label: "Was the issue reported on time?", value: "Issue Reported On Time" },
    { label: "Were internal policies followed?", value: "Internal Policies Followed" },
    { label: "Was CCTV reviewed?", value: "CCTV Reviewed" },
    { label: "Was HR consulted?", value: "HR Consulted" },
    { label: "Was staff suspended?", value: "Staff Suspended" },
    { label: "Is welfare referral needed?", value: "Welfare Referral Needed" },
    { label: "Other", value: "Other" }
  ];

  $w('#dropdownFunnel').options = [
    { label: "Were emails collected?", value: "Emails Collected" },
    { label: "Was senior staff involved?", value: "Senior Staff Involved" },
    { label: "Are notes on file?", value: "Notes on File" },
    { label: "Were backups reviewed?", value: "Backups Reviewed" },
    { label: "Has DPO been notified?", value: "DPO Notified" },
    { label: "Is staff still active?", value: "Staff Still Active" },
    { label: "Other", value: "Other" }
  ];

  $w('#dropdownFunnel3').options = [
    { label: "Internal audit triggered?", value: "Internal Audit Triggered" },
    { label: "IT logs preserved?", value: "IT Logs Preserved" },
    { label: "HR file updated?", value: "HR File Updated" },
    { label: "Disciplinary started?", value: "Disciplinary Started" },
    { label: "Line manager notified?", value: "Line Manager Notified" },
    { label: "Policy training required?", value: "Policy Training Required" },
    { label: "Other", value: "Other" }
  ];
});

function getValue(id) {
  return $w(`#${id}`).value || "";
}

export function submitQueryButton_click(event) {
  console.log("🚨 Submit button clicked");

  const jobTitle = getValue("dropdownJobTitle");
  const timeline = getValue("dropdownTimeline");

  if (!jobTitle || !timeline) {
    $w('#statusText').text = "❌ Please select a job title and timeline before submitting.";
    return;
  }

  const payload = {
    full_name: $w('#inputName').value,
    email: $w('#inputEmail').value,
    query: $w('#inputQuery').value,
    job_title: jobTitle,
    discipline: $w('#inputDiscipline').value,
    timeline: timeline,
    site: getValue("dropdownSiteName"),
    search_type: getValue("dropdownSearchType"),
    funnel_1: getValue("dropdownFunnel1"),
    funnel_2: getValue("dropdownFunnel"),
    funnel_3: getValue("dropdownFunnel3"),
    job_code: Number($w('#inputJobCode').value),
    requires_action_sheet: true,
    source_context: $w('#inputSourceContext').value,
    supervisor_name: $w('#inputSupervisorFullName').value || "Not specified",
    supervisor_email: $w('#inputSupervisorEmail').value || "Not specified",
    hr_email: $w('#inputHrEmail').value || "Not specified"
  };

  console.log("📤 Payload:", payload);
  $w('#statusText').text = "⏳ Sending your query...";

  fetch("https://police-procedures-new.onrender.com/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  })
    .then(res => res.json())
    .then(result => {
      console.log("✅ API Response:", result);
      $w('#statusText').text = result.message || "✅ Your response has been emailed!";
    })
    .catch(err => {
      console.error("❌ Fetch Error:", err);
      $w('#statusText').text = "❌ Failed to send query.";
    });
}