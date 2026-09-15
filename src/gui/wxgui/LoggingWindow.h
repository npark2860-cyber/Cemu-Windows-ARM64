#pragma once

#include "Cemu/Logging/CemuLogging.h"

#include <wx/frame.h>
#include <wx/listbox.h>
#include <wx/combobox.h>
#include "wxgui/components/wxLogCtrl.h"

#include <chrono>
#include <cstdint>
#include <iosfwd>
#include <memory>
#include <string>

class wxLogEvent;
class wxTimer;
class wxTimerEvent;
class wxStaticText;

class LoggingWindow : public wxFrame, public LoggingCallbacks
{
  public:
	LoggingWindow(wxFrame* parent);
	~LoggingWindow();

	void Log(std::string_view filter, std::string_view message) override;
	void Log(std::string_view filter, std::wstring_view message) override;

  private:
	void OnLogMessage(wxLogEvent& event);
	void OnFilterChange(wxCommandEvent& event);
	void OnFilterMessageChange(wxCommandEvent& event);

	void StartHapticRecording();
	void StopHapticRecording();
	void SetHapticMarker(std::string marker);
	void OnHapticTimer(wxTimerEvent& event);
	void WriteHapticSample();
	void UpdateHapticStatus(std::string_view message);

	wxComboBox* m_filter;
	wxLogCtrl* m_log_list;
	wxCheckBox* m_filter_message;

	std::unique_ptr<wxTimer> m_haptic_timer;
	std::unique_ptr<std::ofstream> m_haptic_csv;
	wxStaticText* m_haptic_status{};
	std::chrono::steady_clock::time_point m_haptic_start{};
	std::string m_haptic_marker{"Idle"};
	std::string m_haptic_output_path;
	uint64_t m_haptic_sample_index{};
};
