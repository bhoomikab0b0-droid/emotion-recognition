#include <SPI.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SH110X.h>
#include <FluxGarage_RoboEyes.h>

#define SCREEN_WIDTH  128
#define SCREEN_HEIGHT  64
#define OLED_RESET     -1
#define I2C_ADDRESS  0x3C // Change to 0x3D if your display requires it

Adafruit_SH1106G display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);
RoboEyes<Adafruit_SH1106G> roboEyes(display);

// Fixed RAM-safe buffer for serial input
const byte MAX_INPUT = 20;
char inputBuffer[MAX_INPUT];
byte inputIndex = 0;

void resetEyes() {
  roboEyes.setMood(DEFAULT);
  roboEyes.setCuriosity(OFF);
  roboEyes.setAutoblinker(ON, 3, 2);
  roboEyes.setIdleMode(OFF);
  roboEyes.setWidth(36, 36);
  roboEyes.setHeight(36, 36);
  roboEyes.open();
}

void showHappiness() {
  resetEyes();
  roboEyes.setMood(HAPPY);
  roboEyes.setAutoblinker(ON, 2, 1);
  roboEyes.anim_laugh();
}

void showSadness() {
  resetEyes();
  roboEyes.setMood(TIRED);
  roboEyes.setAutoblinker(ON, 6, 2);
  roboEyes.setPosition(S);
}

void showAnger() {
  resetEyes();
  roboEyes.setMood(ANGRY);
  roboEyes.setAutoblinker(OFF);
}

void showNeutral() {
  resetEyes();
  roboEyes.setMood(DEFAULT);
  roboEyes.setAutoblinker(ON, 3, 2);
  roboEyes.setIdleMode(ON, 4, 2);
}

void showSurprise() {
  resetEyes();
  roboEyes.setHeight(46, 46);
  roboEyes.setWidth(46, 46);
  roboEyes.setAutoblinker(OFF);
  roboEyes.setPosition(N);
}

void showFear() {
  resetEyes();
  roboEyes.setHeight(46, 46);
  roboEyes.setPosition(N);
  roboEyes.anim_confused();
}

void showConfusion() {
  resetEyes();
  roboEyes.setCuriosity(ON);
  roboEyes.anim_confused();
}

void showTired() {
  resetEyes();
  roboEyes.setMood(TIRED);
  roboEyes.setAutoblinker(ON, 2, 1);
}

void showExcited() {
  resetEyes();
  roboEyes.setMood(HAPPY);
  roboEyes.setHeight(42, 42);
  roboEyes.setAutoblinker(ON, 1, 1);
  roboEyes.anim_laugh();
}

void handleCommand(char* cmd) {
  // Convert incoming text to uppercase to match commands
  for (byte i = 0; cmd[i] != '\0'; i++) {
    cmd[i] = toupper(cmd[i]);
  }

  // strcmp_P safely compares the RAM buffer (cmd) to Flash Memory (PSTR)
  if      (strcmp_P(cmd, PSTR("HAPPINESS")) == 0 || strcmp_P(cmd, PSTR("HAPPY")) == 0) { showHappiness(); Serial.println(F("HAPPINESS")); }
  else if (strcmp_P(cmd, PSTR("SADNESS")) == 0   || strcmp_P(cmd, PSTR("SAD")) == 0)   { showSadness();   Serial.println(F("SADNESS"));   }
  else if (strcmp_P(cmd, PSTR("ANGER")) == 0     || strcmp_P(cmd, PSTR("ANGRY")) == 0) { showAnger();     Serial.println(F("ANGER"));     }
  else if (strcmp_P(cmd, PSTR("NEUTRAL")) == 0)                                        { showNeutral();   Serial.println(F("NEUTRAL"));   }
  else if (strcmp_P(cmd, PSTR("SURPRISE")) == 0)                                       { showSurprise();  Serial.println(F("SURPRISE"));  }
  else if (strcmp_P(cmd, PSTR("FEAR")) == 0)                                           { showFear();      Serial.println(F("FEAR"));      }
  else if (strcmp_P(cmd, PSTR("CONFUSION")) == 0 || strcmp_P(cmd, PSTR("CONFUSED")) == 0){ showConfusion(); Serial.println(F("CONFUSION")); }
  else if (strcmp_P(cmd, PSTR("TIRED")) == 0)                                          { showTired();     Serial.println(F("TIRED"));     }
  else if (strcmp_P(cmd, PSTR("EXCITED")) == 0)                                        { showExcited();   Serial.println(F("EXCITED"));   }
  else { 
    Serial.print(F("Unknown command received: [")); 
    Serial.print(cmd); 
    Serial.println(F("]"));
  }
}

void setup() {
  Serial.begin(9600);
  delay(2000);

  if (!display.begin(I2C_ADDRESS, true)) {
    Serial.println(F("Display init failed!"));
    while (true);
  }

  display.clearDisplay();
  display.display();

  roboEyes.begin(SCREEN_WIDTH, SCREEN_HEIGHT, 30);
  roboEyes.setDisplayColors(0, 1);
  roboEyes.open();
  roboEyes.setAutoblinker(ON, 3, 2);

  Serial.println(F("Ready. Type an emotion:"));
  Serial.println(F("HAPPINESS SADNESS ANGER NEUTRAL SURPRISE FEAR CONFUSION TIRED EXCITED"));
}

void loop() {
  roboEyes.update();

  while (Serial.available()) {
    char c = Serial.read();
    
    // Ignore newlines and carriage returns, process string when they hit
    if (c == '\n' || c == '\r') {
      if (inputIndex > 0) {
        inputBuffer[inputIndex] = '\0'; // Add a null terminator to make it a valid string
        handleCommand(inputBuffer);     // Process the command directly
        inputIndex = 0;                 // Reset index for the next word
      }
    } else {
      // Add character only if we haven't reached the buffer limit
      if (inputIndex < MAX_INPUT - 1) {
        inputBuffer[inputIndex] = c;
        inputIndex++;
      }
    }
  }
}