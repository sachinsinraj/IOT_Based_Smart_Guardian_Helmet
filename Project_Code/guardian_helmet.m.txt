
%% ============================================================
% SMART HELMET - IoT ACCIDENT DETECTION SYSTEM
% VERSION 2.1 - FIXED MULTI-SCENARIO SIMULATION
%
% Project:
% IoT-Based Smart Helmet for Accident Detection
% and Real-Time Emergency Location Alert System
%
% Simulated Sensors:
% 1. GPS Speed
% 2. Accelerometer (MPU6050)
% 3. Gyroscope (Pitch, Roll, Yaw)
% 4. Barometric Altitude (BMP280)
%
% Controller: ESP32 (Theoretical Simulation)
%
% TEST SCENARIOS:
% 1. Normal Riding
% 2. Pothole / Sudden Braking
% 3. Actual Accident
%% ============================================================

clear;
clc;
close all;

rng(1);

fprintf('\n');
fprintf('==============================================\n');
fprintf('       SMART HELMET IoT SYSTEM - V2.1\n');
fprintf('==============================================\n');

%% 1. SYSTEM CONFIGURATION

Fs = 10;
dt = 1/Fs;
T = 60;

time = 0:dt:T;
N = length(time);

% Detection thresholds

IMPACT_THRESHOLD = 3.0;
SPEED_DROP_THRESHOLD = 20;
TILT_THRESHOLD = 60;

MIN_CONDITIONS = 2;

windowSize = Fs;

% Emergency settings

warningTime = 20;
riderCancelled = false;

emergencyContact = '+91XXXXXXXXXX';

% Illustrative GPS coordinates

baseLatitude = 28.6139;
baseLongitude = 77.2090;

%% 2. INITIALIZE THREE SCENARIOS

scenarioNames = {
    'NORMAL RIDING'
    'POTHOLE / SUDDEN BRAKING'
    'ACTUAL ACCIDENT'
};

numberOfScenarios = 3;

speed = zeros(numberOfScenarios,N);

Ax = zeros(numberOfScenarios,N);
Ay = zeros(numberOfScenarios,N);
Az = zeros(numberOfScenarios,N);

pitch = zeros(numberOfScenarios,N);
roll = zeros(numberOfScenarios,N);
yaw = zeros(numberOfScenarios,N);

altitude = zeros(numberOfScenarios,N);

%% 3. GENERATE NORMAL SENSOR DATA

for s = 1:numberOfScenarios

    % GPS speed

    speed(s,:) = 50 + ...
        3*sin(time/5) + ...
        randn(1,N)*0.8;

    % Accelerometer

    Ax(s,:) = 0.05 + randn(1,N)*0.03;
    Ay(s,:) = 0.05 + randn(1,N)*0.03;
    Az(s,:) = 1 + randn(1,N)*0.03;

    % Gyroscope / Orientation

    pitch(s,:) = randn(1,N)*2;
    roll(s,:) = randn(1,N)*2;
    yaw(s,:) = randn(1,N)*2;

    % Altitude

    altitude(s,:) = 200 + ...
        0.2*sin(time/10) + ...
        randn(1,N)*0.02;

end

%% 4. SCENARIO 1 - NORMAL RIDING

scenario1 = 1;

% Normal riding.
% No abnormal impact, speed drop or tilt.

%% 5. SCENARIO 2 - POTHOLE / SUDDEN BRAKING

scenario2 = 2;

% A. Simulate pothole impact

potholeIndex = find(time >= 20 & time <= 20.2);

Ax(scenario2,potholeIndex) = 4;
Ay(scenario2,potholeIndex) = 3;
Az(scenario2,potholeIndex) = 4;

% B. Simulate sudden braking

brakeStart = find(time >= 30,1);
brakeEnd = find(time >= 31,1);

speed(scenario2,brakeStart:brakeEnd) = ...
    linspace(50,15,brakeEnd-brakeStart+1);

brakeHoldEnd = find(time >= 33,1);

speed(scenario2,brakeEnd:brakeHoldEnd) = 15;

% No major tilt is simulated.

%% 6. SCENARIO 3 - ACTUAL ACCIDENT

scenario3 = 3;

accidentTime = 40;

accidentIndex = find(time >= accidentTime,1);

% A. Simulate sudden speed reduction

decelerationEnd = find(time >= 41.5,1);

speed(scenario3,accidentIndex:decelerationEnd) = ...
    linspace(50,0,decelerationEnd-accidentIndex+1);

speed(scenario3,decelerationEnd:end) = 0;

% B. Simulate high impact

impactIndices = find( ...
    time >= 40 & time <= 40.5);

Ax(scenario3,impactIndices) = ...
    4 + randn(1,length(impactIndices))*0.2;

Ay(scenario3,impactIndices) = ...
    3 + randn(1,length(impactIndices))*0.2;

Az(scenario3,impactIndices) = ...
    4 + randn(1,length(impactIndices))*0.2;

% C. Simulate helmet orientation change

tiltIndices = find( ...
    time >= 40 & time <= 45);

pitch(scenario3,tiltIndices) = ...
    75 + randn(1,length(tiltIndices))*3;

roll(scenario3,tiltIndices) = ...
    65 + randn(1,length(tiltIndices))*3;

% D. Simulate altitude change

altitudeIndices = find( ...
    time >= 40 & time <= 43);

altitude(scenario3,altitudeIndices) = ...
    altitude(scenario3,altitudeIndices) - ...
    linspace(0,4,length(altitudeIndices));

%% 7. SENSOR DATA PROCESSING

% Resultant acceleration

accelerationMagnitude = sqrt( ...
    Ax.^2 + Ay.^2 + Az.^2);

% Resultant helmet tilt

tiltMagnitude = sqrt( ...
    pitch.^2 + roll.^2);

% Calculate speed reduction over one second

speedDrop = zeros(numberOfScenarios,N);

for s = 1:numberOfScenarios

    for i = windowSize+1:N

        speedDrop(s,i) = ...
            speed(s,i-windowSize) - speed(s,i);

    end

end

% Calculate altitude reduction

altitudeDrop = zeros(numberOfScenarios,N);

for s = 1:numberOfScenarios

    for i = 2:N

        altitudeDrop(s,i) = ...
            altitude(s,i-1) - altitude(s,i);

    end

end

%% 8. DETECT ABNORMAL SENSOR CONDITIONS

impactDetected = ...
    accelerationMagnitude >= IMPACT_THRESHOLD;

speedDropDetected = ...
    speedDrop >= SPEED_DROP_THRESHOLD;

tiltDetected = ...
    tiltMagnitude >= TILT_THRESHOLD;

%% 9. MULTI-SENSOR ACCIDENT DETECTION

conditionsDetected = zeros(numberOfScenarios,N);

accidentDetected = false(numberOfScenarios,N);

for s = 1:numberOfScenarios

    for i = 1:N

        conditionsDetected(s,i) = ...
            double(impactDetected(s,i)) + ...
            double(speedDropDetected(s,i)) + ...
            double(tiltDetected(s,i));

        if conditionsDetected(s,i) >= MIN_CONDITIONS

            accidentDetected(s,i) = true;

        end

    end

end

%% 10. FIND FIRST ACCIDENT DETECTION
% FIX: Use zero when no accident is detected.
% This avoids assigning an empty array to one element.

firstAccidentIndex = zeros(1,numberOfScenarios);

for s = 1:numberOfScenarios

    detectedIndex = find(accidentDetected(s,:),1);

    if ~isempty(detectedIndex)

        firstAccidentIndex(s) = detectedIndex;

    else

        firstAccidentIndex(s) = 0;

    end

end

%% 11. DISPLAY SCENARIO RESULTS

fprintf('\n');
fprintf('==============================================\n');
fprintf('             SCENARIO TEST RESULTS\n');
fprintf('==============================================\n');

for s = 1:numberOfScenarios

    fprintf('\nSCENARIO: %s\n',scenarioNames{s});

    if firstAccidentIndex(s) == 0

        fprintf('Result: NO ACCIDENT DETECTED\n');
        fprintf('System: SAFE\n');

    else

        idx = firstAccidentIndex(s);

        fprintf('Result: POSSIBLE ACCIDENT DETECTED\n');

        fprintf('Detection Time: %.2f seconds\n', ...
            time(idx));

        fprintf('Speed: %.2f km/h\n', ...
            speed(s,idx));

        fprintf('Acceleration: %.2f g\n', ...
            accelerationMagnitude(s,idx));

        fprintf('Tilt: %.2f degrees\n', ...
            tiltMagnitude(s,idx));

        fprintf('Abnormal Conditions: %d / 3\n', ...
            conditionsDetected(s,idx));

    end

end

%% 12. EMERGENCY VERIFICATION

fprintf('\n');
fprintf('==============================================\n');
fprintf('           EMERGENCY VERIFICATION\n');
fprintf('==============================================\n');

if firstAccidentIndex(scenario3) ~= 0

    detectedIndex = firstAccidentIndex(scenario3);

    detectedTime = time(detectedIndex);

    fprintf('\nACTUAL ACCIDENT DETECTED!\n');

    fprintf('Detection Time: %.2f seconds\n', ...
        detectedTime);

    fprintf('BUZZER ACTIVATED!\n');

    fprintf('Rider has %d seconds to cancel alert.\n', ...
        warningTime);

    if riderCancelled

        fprintf('\n');
        fprintf('ALERT CANCELLED BY RIDER.\n');
        fprintf('No emergency message generated.\n');

    else

        fprintf('\n');
        fprintf('NO RESPONSE FROM RIDER.\n');

        fprintf('EMERGENCY ALERT INITIATED.\n');

        %% 13. GPS LOCATION

        latitude = baseLatitude + ...
            0.0001*sin(detectedTime);

        longitude = baseLongitude + ...
            0.0001*cos(detectedTime);

        fprintf('\n');
        fprintf('GPS LOCATION:\n');

        fprintf('Latitude: %.6f\n',latitude);
        fprintf('Longitude: %.6f\n',longitude);

        %% 14. GOOGLE MAPS LINK

        googleMapsLink = sprintf( ...
            'https://maps.google.com/?q=%.6f,%.6f', ...
            latitude,longitude);

        fprintf('\nGOOGLE MAPS LOCATION:\n');

        fprintf('%s\n',googleMapsLink);

        %% 15. EMERGENCY MESSAGE

        emergencyMessage = sprintf([ ...
            'EMERGENCY ALERT!\n' ...
            'A possible motorcycle accident has been detected.\n' ...
            'Please check the rider immediately.\n' ...
            'Location: %s'],googleMapsLink);

        fprintf('\n');
        fprintf('==============================================\n');
        fprintf('             EMERGENCY ALERT\n');
        fprintf('==============================================\n');

        fprintf('Recipient: %s\n\n',emergencyContact);

        fprintf('%s\n',emergencyMessage);

        fprintf('\nSIMULATED ALERT GENERATED SUCCESSFULLY.\n');

    end

else

    fprintf('No accident detected in the actual accident test.\n');

end

%% 16. SENSOR GRAPHS FOR ALL SCENARIOS

for s = 1:numberOfScenarios

    figure('Name',scenarioNames{s}, ...
        'NumberTitle','off');

    % GPS SPEED

    subplot(4,1,1);

    plot(time,speed(s,:),'b','LineWidth',1.5);

    hold on;

    if firstAccidentIndex(s) ~= 0

        xline(time(firstAccidentIndex(s)), ...
            '--r','Accident');

    end

    ylabel('Speed (km/h)');
    xlabel('Time (seconds)');

    title([scenarioNames{s} ' - GPS SPEED']);

    grid on;

    % ACCELERATION

    subplot(4,1,2);

    plot(time,accelerationMagnitude(s,:), ...
        'LineWidth',1.5);

    hold on;

    yline(IMPACT_THRESHOLD,'--r','Impact Threshold');

    if firstAccidentIndex(s) ~= 0

        xline(time(firstAccidentIndex(s)),'--r');

    end

    ylabel('Acceleration (g)');
    xlabel('Time (seconds)');

    title('ACCELEROMETER');

    grid on;

    % TILT

    subplot(4,1,3);

    plot(time,tiltMagnitude(s,:), ...
        'LineWidth',1.5);

    hold on;

    yline(TILT_THRESHOLD,'--r','Tilt Threshold');

    if firstAccidentIndex(s) ~= 0

        xline(time(firstAccidentIndex(s)),'--r');

    end

    ylabel('Tilt (degrees)');
    xlabel('Time (seconds)');

    title('GYROSCOPE / ORIENTATION');

    grid on;

    % ALTITUDE

    subplot(4,1,4);

    plot(time,altitude(s,:),'LineWidth',1.5);

    ylabel('Altitude (m)');
    xlabel('Time (seconds)');

    title('BAROMETRIC ALTITUDE');

    grid on;

end

%% 17. COMPARE ALL THREE SCENARIOS

figure('Name','Multi-Scenario Comparison', ...
    'NumberTitle','off');

for s = 1:numberOfScenarios

    subplot(3,1,s);

    plot(time,conditionsDetected(s,:), ...
        'LineWidth',1.5);

    hold on;

    yline(MIN_CONDITIONS, ...
        '--r','Detection Threshold');

    ylabel('Conditions');
    xlabel('Time (seconds)');

    title(scenarioNames{s});

    ylim([0 3.5]);

    grid on;

end

%% 18. FINAL SYSTEM REPORT

fprintf('\n');
fprintf('==============================================\n');
fprintf('              FINAL SYSTEM REPORT\n');
fprintf('==============================================\n');

% TEST 1

fprintf('\nTEST 1 - NORMAL RIDING:\n');

if firstAccidentIndex(1) == 0

    fprintf('PASS: No false accident detected.\n');

else

    fprintf('FAIL: False accident detected.\n');

end

% TEST 2

fprintf('\nTEST 2 - POTHOLE / SUDDEN BRAKING:\n');

if firstAccidentIndex(2) == 0

    fprintf('PASS: False alarm prevented.\n');

else

    fprintf('FAIL: False accident detected.\n');

end

% TEST 3

fprintf('\nTEST 3 - ACTUAL ACCIDENT:\n');

if firstAccidentIndex(3) ~= 0

    fprintf('PASS: Accident successfully detected.\n');

else

    fprintf('FAIL: Accident not detected.\n');

end

fprintf('\n');
fprintf('==============================================\n');
fprintf('       SMART HELMET SIMULATION COMPLETED\n');
fprintf('==============================================\n');
