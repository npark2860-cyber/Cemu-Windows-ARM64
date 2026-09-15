#include "wxgui/LoggingWindow.h"

#include "Cafe/CafeSystem.h"
#include "Cemu/Logging/CemuLogging.h"
#include "config/ActiveSettings.h"
#include "input/InputManager.h"
#include "input/emulated/VPADController.h"
#include "wxgui/helpers/wxLogEvent.h"

#include <wx/button.h>
#include <wx/sizer.h>
#include <wx/statbox.h>
#include <wx/stattext.h>
#include <wx/timer.h>
#include <wx/wupdlock.h>

#include <ctime>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <system_error>

wxDEFINE_EVENT(EVT_LOG, wxLogEvent);

namespace
{
constexpr int kHapticSamplePeriodMs = 16;

std::string MakeHapticSessionFilename()
{
	const auto now = std::chrono::system_clock::now();
	const std::time_t nowTime = std::chrono::system_clock::to_time_t(now);
	std::tm localTime{};
#if BOOST_OS_WINDOWS
	localtime_s(&localTime, &nowTime);
#else
	localtime_r(&nowTime, &localTime);
#endif

	std::ostringstream name;
	name << "haptic_" << std::put_time(&localTime, "%Y%m%d_%H%M%S") << ".csv";
	return name.str();
}
} // namespace

LoggingWindow::LoggingWindow(wxFrame* parent)
	: wxFrame(parent, wxID_ANY, _("Logging window + Haptic State Logger"), wxDefaultPosition, wxSize(920, 760), wxDEFAULT_FRAME_STYLE | wxTAB_TRAVERSAL)
{
	auto* sizer = new wxBoxSizer(wxVERTICAL);
	{
		auto filter_row = new wxBoxSizer(wxHORIZONTAL);

		filter_row->Add(new wxStaticText(this, wxID_ANY, _("Filter")), 0, wxALIGN_CENTER_VERTICAL | wxALL, 5);

		wxString choices[] = {"Unsupported APIs calls", "Coreinit Logging", "Coreinit File-Access", "Coreinit Thread-Synchronization", "Coreinit Memory", "Coreinit MP", "Coreinit Thread", "nn::nfp", "GX2", "Audio", "Input", "Socket", "Save", "H264", "Graphic pack patches", "Texture cache", "Texture readback", "OpenGL debug output", "Vulkan validation layer", "Metal debug output"};
		m_filter = new wxComboBox(this, wxID_ANY, wxEmptyString, wxDefaultPosition, wxDefaultSize, std::size(choices), choices);
		m_filter->Bind(wxEVT_COMBOBOX, &LoggingWindow::OnFilterChange, this);
		m_filter->Bind(wxEVT_TEXT, &LoggingWindow::OnFilterChange, this);
		filter_row->Add(m_filter, 1, wxALL, 5);

		m_filter_message = new wxCheckBox(this, wxID_ANY, _("Filter messages"));
		m_filter_message->Bind(wxEVT_CHECKBOX, &LoggingWindow::OnFilterMessageChange, this);
		filter_row->Add(m_filter_message, 0, wxALIGN_CENTER_VERTICAL | wxALL, 5);

		sizer->Add(filter_row, 0, wxEXPAND, 5);
	}

	{
		auto* hapticBox = new wxStaticBoxSizer(wxVERTICAL, this, _("Haptic State Logger - BOTW diagnostic"));
		auto* controlRow = new wxBoxSizer(wxHORIZONTAL);

		auto* record = new wxButton(this, wxID_ANY, _("REC"));
		record->Bind(wxEVT_BUTTON, [this](wxCommandEvent&) { StartHapticRecording(); });
		controlRow->Add(record, 0, wxALL, 4);

		auto* stop = new wxButton(this, wxID_ANY, _("STOP"));
		stop->Bind(wxEVT_BUTTON, [this](wxCommandEvent&) { StopHapticRecording(); });
		controlRow->Add(stop, 0, wxALL, 4);

		controlRow->AddSpacer(12);

		auto addMarkerButton = [this, controlRow](const wxString& label, std::string marker) {
			auto* button = new wxButton(this, wxID_ANY, label);
			button->Bind(wxEVT_BUTTON, [this, marker = std::move(marker)](wxCommandEvent&) { SetHapticMarker(marker); });
			controlRow->Add(button, 0, wxALL, 4);
		};

		addMarkerButton(_("Idle"), "Idle");
		addMarkerButton(_("Bow"), "Bow");
		addMarkerButton(_("Horse"), "Horse");
		addMarkerButton(_("Master Cycle"), "MasterCycle");
		addMarkerButton(_("Combat"), "Combat");

		hapticBox->Add(controlRow, 0, wxEXPAND | wxLEFT | wxRIGHT, 4);

		m_haptic_status = new wxStaticText(this, wxID_ANY,
			_("Ready. Launch BOTW, press REC, then mark each action while playing."));
		hapticBox->Add(m_haptic_status, 0, wxEXPAND | wxLEFT | wxRIGHT | wxBOTTOM, 8);

		sizer->Add(hapticBox, 0, wxEXPAND | wxLEFT | wxRIGHT | wxBOTTOM, 5);
	}

	m_log_list = new wxLogCtrl(this, wxID_ANY, wxDefaultPosition, wxDefaultSize, wxScrolledWindowStyle, true);
	sizer->Add(m_log_list, 1, wxALL | wxEXPAND, 5);

	this->SetSizer(sizer);
	this->Layout();

	this->Bind(EVT_LOG, &LoggingWindow::OnLogMessage, this);

	m_haptic_timer = std::make_unique<wxTimer>(this);
	this->Bind(wxEVT_TIMER, &LoggingWindow::OnHapticTimer, this, m_haptic_timer->GetId());

	cemuLog_setCallbacks(this);
}

LoggingWindow::~LoggingWindow()
{
	StopHapticRecording();
	if (m_haptic_timer)
		this->Unbind(wxEVT_TIMER, &LoggingWindow::OnHapticTimer, this, m_haptic_timer->GetId());
	this->Unbind(EVT_LOG, &LoggingWindow::OnLogMessage, this);

	cemuLog_clearCallbacks();
}

void LoggingWindow::Log(std::string_view filter, std::string_view message)
{
	wxLogEvent event(std::string{filter}, std::string{message});
	OnLogMessage(event);
}

void LoggingWindow::Log(std::string_view filter, std::wstring_view message)
{
	wxLogEvent event(std::string{filter}, std::wstring{message});
	OnLogMessage(event);
}

void LoggingWindow::OnLogMessage(wxLogEvent& event)
{
	m_log_list->PushEntry(event.GetFilter(), event.GetMessage());
}

void LoggingWindow::OnFilterChange(wxCommandEvent& event)
{
	m_log_list->SetActiveFilter(m_filter->GetValue().utf8_string());
	event.Skip();
}

void LoggingWindow::OnFilterMessageChange(wxCommandEvent& event)
{
	m_log_list->SetFilterMessage(m_filter_message->GetValue());
	event.Skip();
}

void LoggingWindow::UpdateHapticStatus(std::string_view message)
{
	if (m_haptic_status)
		m_haptic_status->SetLabel(wxString::FromUTF8(message));
}

void LoggingWindow::StartHapticRecording()
{
	if (!CafeSystem::IsTitleRunning())
	{
		UpdateHapticStatus("No Wii U title is running. Launch BOTW first.");
		return;
	}

	StopHapticRecording();

	const auto outputDir = ActiveSettings::GetUserDataPath("haptic_diagnostics");
	std::error_code ec;
	std::filesystem::create_directories(outputDir, ec);
	if (ec)
	{
		UpdateHapticStatus("Failed to create haptic_diagnostics output directory.");
		return;
	}

	const auto outputPath = outputDir / MakeHapticSessionFilename();
	m_haptic_csv = std::make_unique<std::ofstream>(outputPath, std::ios::out | std::ios::trunc);
	if (!m_haptic_csv->is_open())
	{
		m_haptic_csv.reset();
		UpdateHapticStatus("Failed to create haptic diagnostic CSV.");
		return;
	}

	m_haptic_output_path = outputPath.string();
	m_haptic_marker = "Idle";
	m_haptic_sample_index = 0;
	m_haptic_start = std::chrono::steady_clock::now();

	*m_haptic_csv
		<< "sample,time_ms,title_id,marker,lx,ly,rx,ry,zl,zr,a,b,x,y,l,r,zl_btn,zr_btn,plus,minus\n";
	m_haptic_csv->flush();

	m_haptic_timer->Start(kHapticSamplePeriodMs);
	UpdateHapticStatus("REC active | marker=Idle | output=haptic_diagnostics/" + outputPath.filename().string());
}

void LoggingWindow::StopHapticRecording()
{
	if (m_haptic_timer && m_haptic_timer->IsRunning())
		m_haptic_timer->Stop();

	if (!m_haptic_csv)
		return;

	m_haptic_csv->flush();
	m_haptic_csv->close();
	m_haptic_csv.reset();

	UpdateHapticStatus("Recording stopped | samples=" + std::to_string(m_haptic_sample_index) +
		" | saved=" + m_haptic_output_path);
}

void LoggingWindow::SetHapticMarker(std::string marker)
{
	m_haptic_marker = std::move(marker);
	if (m_haptic_csv)
	{
		const auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(
			std::chrono::steady_clock::now() - m_haptic_start).count();
		*m_haptic_csv << "#MARKER," << elapsed << "," << m_haptic_marker << "\n";
		m_haptic_csv->flush();
		UpdateHapticStatus("REC active | marker=" + m_haptic_marker +
			" | samples=" + std::to_string(m_haptic_sample_index));
	}
	else
	{
		UpdateHapticStatus("Marker selected: " + m_haptic_marker + " (press REC to record)");
	}
}

void LoggingWindow::OnHapticTimer(wxTimerEvent& event)
{
	if (m_haptic_csv)
		WriteHapticSample();
	event.Skip();
}

void LoggingWindow::WriteHapticSample()
{
	if (!m_haptic_csv || !CafeSystem::IsTitleRunning())
		return;

	const auto vpad = InputManager::instance().get_vpad_controller(0);
	if (!vpad)
	{
		if ((m_haptic_sample_index % 60) == 0)
			UpdateHapticStatus("REC active, but VPAD controller 1 is not configured.");
		++m_haptic_sample_index;
		return;
	}

	const auto leftStick = vpad->get_axis();
	const auto rightStick = vpad->get_rotation();
	const auto triggers = vpad->get_trigger();
	const auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(
		std::chrono::steady_clock::now() - m_haptic_start).count();
	const auto titleId = CafeSystem::GetForegroundTitleId();

	auto down = [&vpad](VPADController::ButtonId id) -> int {
		return vpad->is_mapping_down(id) ? 1 : 0;
	};

	*m_haptic_csv << std::fixed << std::setprecision(6)
		<< m_haptic_sample_index << ','
		<< elapsed << ','
		<< "0x" << std::hex << titleId << std::dec << ','
		<< m_haptic_marker << ','
		<< leftStick.x << ',' << leftStick.y << ','
		<< rightStick.x << ',' << rightStick.y << ','
		<< triggers.x << ',' << triggers.y << ','
		<< down(VPADController::kButtonId_A) << ','
		<< down(VPADController::kButtonId_B) << ','
		<< down(VPADController::kButtonId_X) << ','
		<< down(VPADController::kButtonId_Y) << ','
		<< down(VPADController::kButtonId_L) << ','
		<< down(VPADController::kButtonId_R) << ','
		<< down(VPADController::kButtonId_ZL) << ','
		<< down(VPADController::kButtonId_ZR) << ','
		<< down(VPADController::kButtonId_Plus) << ','
		<< down(VPADController::kButtonId_Minus) << '\n';

	++m_haptic_sample_index;
	if ((m_haptic_sample_index % 60) == 0)
	{
		m_haptic_csv->flush();
		UpdateHapticStatus("REC active | marker=" + m_haptic_marker +
			" | samples=" + std::to_string(m_haptic_sample_index));
	}
}
