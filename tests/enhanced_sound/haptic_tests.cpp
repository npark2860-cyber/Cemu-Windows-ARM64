#include "Cafe/OS/common/EnhancedHapticMixer.h"
#include "Cafe/OS/common/EnhancedSoundRouter.h"
#include <cstdlib>
#include <iostream>
#include <thread>

using namespace EnhancedHapticEngine;
using namespace std::chrono_literals;

static void Require(bool ok, const char* message)
{
	if (!ok) { std::cerr << message << '\n'; std::exit(1); }
}

static auto MakeClip(uint8_t low, uint8_t high, bool loop = true)
{
	auto clip = std::make_shared<Clip>();
	clip->sampleRateHz = 100;
	clip->samples = {{low, 96, high, 139}, {low, 96, high, 139}};
	if (loop) clip->loop = Loop{0, 2, 0};
	return clip;
}

int main(int argc, char** argv)
{
	if (argc > 1)
	{
		size_t count = 0;
		for (const auto& file : std::filesystem::directory_iterator(argv[1]))
		{
			if (file.path().extension() != ".bnvib") continue;
			Clip clip;
			Require(LoadBnvib(file.path(), clip), "pack BNVIB must parse in production loader");
			++count;
		}
		Require(count == 11, "pack includes all eleven haptic patterns");
	}
	const auto t = Mixer::Clock::time_point{};
	{
		Mixer pending;
		const auto id = pending.Play(MakeClip(90, 20, false), 1, true, t);
		Require(pending.Tick(t)->lowLevel == 0, "bound clip waits silently");
		pending.Tick(t + 200ms);
		Require(pending.IsActive(), "pending snapshot must not consume a short clip");
		pending.Update(id, 1, t + 201ms);
		Require(pending.Tick(t + 201ms)->lowLevel == 90, "first snapshot starts the full clip");
		pending.Tick(t + 221ms);
		Require(!pending.IsActive(), "bound one-shot still ends naturally");
		// Legacy UI one-shots need no AX snapshot/lease and finish independently.
		pending.Play(MakeClip(90, 20, false), 0.4f, false, t);
		Require(pending.Tick(t)->lowLevel == 36, "legacy UI starts without snapshot");
		Require(pending.Tick(t + 20ms)->lowLevel == 0, "legacy UI completes itself");
	}
	Mixer mixer;
	const auto engine = mixer.Play(MakeClip(100, 30), 1, true, t);
	Require(engine != 0, "playback allocation");
	Require(mixer.Tick(t)->lowLevel == 0, "no blast before AX snapshot");
	mixer.Update(engine, 0.5f, t);
	Require(mixer.Tick(t)->lowLevel == 50, "gain updates within the same sample");
	mixer.Update(engine, 0, t + 1ms);
	Require(mixer.Tick(t + 1ms)->lowLevel == 0, "inaudible source mutes");
	mixer.Update(engine, 1, t + 2ms);
	Require(mixer.Tick(t + 2ms)->lowLevel == 100, "muted loop resumes");
	const auto action = mixer.Play(MakeClip(180, 80, false), 1, false, t + 2ms);
	Require(mixer.Tick(t + 2ms)->lowLevel == 180, "overlap combines by maximum");
	Require(mixer.Tick(t + 22ms)->lowLevel == 100, "one-shot ends without losing loop");
	mixer.Stop(action);
	Require(!mixer.Tick(t + 22ms), "stale stop cannot stop unrelated voice");
	Require(mixer.Tick(t + 102ms)->lowLevel == 0, "AX lease expiry outputs zero");
	mixer.Update(engine, 1, t + 103ms);
	Require(mixer.Tick(t + 103ms)->lowLevel == 100, "resume renews lease");
	mixer.Stop(engine);
	const auto replacement = mixer.Play(MakeClip(70, 20), 1, true, t + 104ms);
	Require(replacement != engine, "voice reuse gets distinct generation");
	mixer.Update(replacement, 1, t + 104ms);
	mixer.Update(engine, 0, t + 104ms);
	mixer.Stop(engine);
	Require(mixer.Tick(t + 104ms)->lowLevel == 70, "stale update/stop cannot affect replacement");
	Require(mixer.Tick(t + 104ms, true)->lowLevel == 70, "reconnect forces output");
	mixer.Stop();
	Require(mixer.Tick(t + 104ms)->lowLevel == 0 && !mixer.IsActive(), "global stop");
	Require(!mixer.Tick(t + 105ms), "deduplicate unchanged output");
	const auto invalidGain = mixer.Play(MakeClip(100, 100), std::numeric_limits<float>::quiet_NaN());
	Require(invalidGain && mixer.Tick(t, true)->lowLevel == 0, "nonfinite gain mutes");
	mixer.Stop();
	for (size_t i = 0; i < Mixer::Capacity; ++i)
		Require(mixer.Play(MakeClip(100, 20), 1) != 0, "bounded mixer allocation");
	Require(mixer.Play(MakeClip(100, 20), 1) == 0, "capacity does not evict existing voices");
	mixer.Stop();
	// Exercise the production synchronization under concurrent service/API traffic.
	std::thread worker([&] { for (int i = 0; i < 10000; ++i) mixer.Tick(); });
	for (int i = 0; i < 1000; ++i)
	{
		const auto id = mixer.Play(MakeClip(70, 20), 1, true);
		mixer.Update(id, 0.5f);
		mixer.Stop(id);
	}
	worker.join();
	Require(!mixer.IsActive(), "concurrent playback cleanup");

	using namespace EnhancedSoundRouter;
	RouteRule rule;
	rule.sourcePattern = "*";
	rule.hapticPath = "test.bnvib";
	RegisterRouteTable("test", {rule});
	auto constant = Resolve("sound", "track");
	Require(constant && !constant->hapticFollowTv, "legacy default constant gain");
	rule.hapticFollowTv = true;
	RegisterRouteTable("test", {rule});
	auto spatial = Resolve("sound", "track");
	Require(spatial && spatial->hapticFollowTv && !Equivalent(*constant, *spatial),
		"route cache invalidates and ambiguity comparison includes volume policy");
	UnregisterRouteTable("test");
	std::cout << "Haptic mixer and route tests PASS\n";
}
