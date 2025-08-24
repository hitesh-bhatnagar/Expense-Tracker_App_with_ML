using System;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using CsvHelper;
using ExpenseTracker.Data;
using ExpenseTracker.Models;
using ExpenseTracker.ViewModels;
using Microsoft.Win32;
using System.Reflection;

namespace ExpenseTracker
{
    public partial class MainWindow : Window
    {
        private bool _suppressHandler = false;

        public MainWindow()
        {
            InitializeComponent();
            DataContext = new MainViewModel();
        }

        // Export expenses to CSV
        private void ExportCsv_Click(object sender, RoutedEventArgs e)
        {
            var saveFileDialog = new SaveFileDialog
            {
                Filter = "CSV files (*.csv)|*.csv",
                FileName = "Expenses.csv"
            };

            if (saveFileDialog.ShowDialog() == true)
            {
                try
                {
                    using (var writer = new StreamWriter(saveFileDialog.FileName))
                    using (var csv = new CsvWriter(writer, CultureInfo.InvariantCulture))
                    {
                        csv.Context.RegisterClassMap<ExpenseMap>(); // Register the map
                        using var context = new AppDbContext();
                        var allExpenses = context.Expenses.ToList();
                        csv.WriteRecords(allExpenses);
                    }


                    MessageBox.Show("Expenses exported successfully!", "Export Complete", MessageBoxButton.OK, MessageBoxImage.Information);
                }
                catch (Exception ex)
                {
                    MessageBox.Show("Error exporting data: " + ex.Message, "Error", MessageBoxButton.OK, MessageBoxImage.Error);
                }
            }
        }

        public void RunAnalyzer_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                // 1) Locate the ML folder relative to the deployed app, not the solution
                string baseDir = AppContext.BaseDirectory; // works in Debug + Publish
                string mlFolder = Path.Combine(baseDir, "ML");
                Directory.CreateDirectory(mlFolder);

                string csvPath = Path.Combine(mlFolder, "expenses.csv");
                string htmlPath = Path.Combine(mlFolder, "trend.html");

                // 2) Export DB -> CSV (your existing logic)
                using (var context = new AppDbContext())
                {
                    var expenses = context.Expenses.OrderBy(exp => exp.Date).ToList();
                    using (var writer = new StreamWriter(csvPath))
                    {
                        writer.WriteLine("Id,Description,Amount,Date");
                        foreach (var exp in expenses)
                            writer.WriteLine($"{exp.Id},\"{exp.Description}\",{exp.Amount},{exp.Date:yyyy-MM-dd}");
                    }
                }

                // 3) Decide how to run the analyzer (A: venv python OR B: analyzer.exe)
                // ------- OPTION A: run the virtualenv python -------
                string venvPython = Path.Combine(mlFolder, ".venv", "Scripts", "python.exe");
                string analyzerScript = Path.Combine(mlFolder, "analyzer.py");
                bool useVenv = File.Exists(venvPython) && File.Exists(analyzerScript);

                // ------- OPTION B: run the bundled EXE (PyInstaller) -------
                string analyzerExe = Path.Combine(mlFolder, "analyzer.exe");
                bool useExe = File.Exists(analyzerExe);

                ProcessStartInfo psi;

                if (useExe)
                {
                    // Best UX: no Python required
                    psi = new ProcessStartInfo
                    {
                        FileName = analyzerExe,
                        Arguments = $"--out \"{htmlPath}\" --open",
                        WorkingDirectory = mlFolder,
                        UseShellExecute = false,
                        RedirectStandardOutput = true,
                        RedirectStandardError = true,
                        CreateNoWindow = true
                    };
                }
                else if (useVenv)
                {
                    // Falls back to your packaged venv
                    psi = new ProcessStartInfo
                    {
                        FileName = venvPython,
                        Arguments = $"\"{analyzerScript}\" --out \"{htmlPath}\" --open",
                        WorkingDirectory = mlFolder,
                        UseShellExecute = false,
                        RedirectStandardOutput = true,
                        RedirectStandardError = true,
                        CreateNoWindow = true
                    };
                }
                else
                {
                    MessageBox.Show(
                        "Analyzer not found.\n\nEither include ML\\analyzer.exe (recommended)\n" +
                        "or ML\\.venv\\Scripts\\python.exe and ML\\analyzer.py in your build.",
                        "Analyzer Missing", MessageBoxButton.OK, MessageBoxImage.Warning);
                    return;
                }

                // 4) Run and capture output (filter noisy INFO)
                string stdOut, stdErr;
                using (var p = Process.Start(psi))
                {
                    stdOut = p.StandardOutput.ReadToEnd();
                    stdErr = p.StandardError.ReadToEnd();
                    p.WaitForExit();
                }

                string filtered = string.Join("\n",
                    stdErr.Split('\n')
                          .Where(line => !line.Contains("cmdstanpy - INFO"))
                          .Where(line => !string.IsNullOrWhiteSpace(line)));

                if (!string.IsNullOrEmpty(filtered))
                {
                    MessageBox.Show("Python error:\n" + filtered, "Analyzer Error",
                        MessageBoxButton.OK, MessageBoxImage.Error);
                    return;
                }

                // 5) If the script didn’t auto-open, open ourselves
                if (File.Exists(htmlPath))
                {
                    Process.Start(new ProcessStartInfo
                    {
                        FileName = htmlPath,
                        UseShellExecute = true
                    });
                }
                else
                {
                    MessageBox.Show("trend.html was not generated!", "Error",
                        MessageBoxButton.OK, MessageBoxImage.Error);
                    return;
                }

                MessageBox.Show("Analysis complete! Report opened in browser.", "Analyzer",
                    MessageBoxButton.OK, MessageBoxImage.Information);
            }
            catch (Exception ex)
            {
                MessageBox.Show("Error running analyzer: " + ex.Message, "Error",
                    MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        // Handle row edits to save changes to DB
        private void ExpenseGrid_RowEditEnding(object sender, DataGridRowEditEndingEventArgs e)
        {
            if (_suppressHandler)
                return;

            _suppressHandler = true;

            try
            {
                if (e.EditAction == DataGridEditAction.Commit)
                {
                    var grid = sender as DataGrid;

                    grid.CommitEdit(DataGridEditingUnit.Row, true);

                    if (e.Row.Item is Expense editedExpense)
                    {
                        using var context = new AppDbContext();

                        var existing = context.Expenses.Find(editedExpense.Id);

                        if (existing != null)
                        {
                            existing.Description = editedExpense.Description;
                            existing.Amount = editedExpense.Amount;

                            // Specify UTC kind for date
                            existing.Date = DateTime.SpecifyKind(editedExpense.Date, DateTimeKind.Utc);
                        }
                        else
                        {
                            context.Expenses.Add(editedExpense);
                        }

                        context.SaveChanges();

                        if (DataContext is MainViewModel vm)
                        {
                            vm.LoadData();
                        }
                    }
                }
            }
            finally
            {
                _suppressHandler = false;
            }
        }
    }
}
